"""Loop 3 — External Feedback Loop.

The outer loop: gather user feedback → LLM summarizes into product changes →
update vision / spec → re-trigger Loop 2 (which re-triggers Loop 1).
Runs on the order of *days*.

Feedback is collected via a lightweight web UI (port 5001) that stores items
in a JSON file. The loop polls this file and processes feedback when the
developer triggers it.
"""

from __future__ import annotations

import json
import subprocess
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Any

import requests as http_requests

from loop_engineering.config import settings
from loop_engineering.ollama_client import OllamaClient
from loop_engineering.prompts import EXTERNAL_FEEDBACK_SYSTEM
from loop_engineering.loops.developer import DeveloperLoop
from loop_engineering import display
from loop_engineering.tracker import LoopTracker


FEEDBACK_UI_PORT = 5001


class ExternalLoop:
    """Loop 3: user feedback → vision update → re-trigger developer loop.

    Parameters
    ----------
    spec_path : Path | None
        Path to the product spec markdown file.
    workspace : Path | None
        Where generated code lives.
    max_rounds : int | None
        Max external feedback rounds.
    feedback_path : Path | None
        JSON file where feedback is collected.
    """

    def __init__(
        self,
        spec_path: Path | None = None,
        workspace: Path | None = None,
        max_rounds: int | None = None,
        feedback_path: Path | None = None,
        tracker: LoopTracker | None = None,
    ) -> None:
        self.spec_path = spec_path or settings.spec_path
        self.workspace = workspace or settings.workspace
        self.max_rounds = max_rounds or settings.max_external_rounds
        self.feedback_path = feedback_path or (self.workspace.parent / "feedback.json")
        self.client = OllamaClient()
        self.tracker = tracker or LoopTracker()

    def run(self) -> None:
        """Run the full 3-loop cycle."""
        for round_num in range(1, self.max_rounds + 1):
            display.loop_header("external", round_num)

            # ── Step 1: Run developer loop (which runs agentic loop inside) ──
            display.info("Starting developer loop (includes agentic coding)...")
            dev_loop = DeveloperLoop(
                spec_path=self.spec_path,
                workspace=self.workspace,
                tracker=self.tracker,
            )
            dev_loop.run()

            # ── Step 2: Launch feedback UI and wait for feedback ──
            display.info(
                f"Launching feedback web UI at http://localhost:{FEEDBACK_UI_PORT}"
            )
            display.info(
                "Share this URL with testers. They can submit feedback in the browser."
            )

            ui_proc = self._start_feedback_ui()

            try:
                feedback_items = self._wait_for_feedback(round_num)
            finally:
                self._stop_feedback_ui(ui_proc)

            if not feedback_items:
                display.success("No external feedback. All loops complete!")
                self.tracker.record(
                    loop="external",
                    iteration=round_num,
                    success=True,
                    summary="No external feedback — session complete.",
                )
                break

            # ── Step 3: Summarize feedback into spec changes ───
            display.info(
                f"Summarizing {len(feedback_items)} feedback item(s) with LLM..."
            )
            current_spec = self.spec_path.read_text()
            updated_spec = self._incorporate_feedback(
                current_spec, feedback_items, round_num
            )
            self.spec_path.write_text(updated_spec)
            display.success("Spec updated with external feedback.")

            self.tracker.record(
                loop="external",
                iteration=round_num,
                success=True,
                summary=f"{len(feedback_items)} feedback items incorporated.",
                extra={"feedback_count": len(feedback_items)},
            )
        else:
            display.warning(f"Reached max external rounds ({self.max_rounds}).")

        # ── Final summary ──────────────────────────────────────
        display.summary_table(self.tracker.all())

    # ── Feedback UI management ──────────────────────────────────

    def _start_feedback_ui(self) -> subprocess.Popen | None:
        """Launch the feedback web UI as a subprocess."""
        try:
            proc = subprocess.Popen(
                [
                    sys.executable, "-c",
                    (
                        "from loop_engineering.feedback_ui import run_feedback_server; "
                        "from pathlib import Path; "
                        f"run_feedback_server(Path('{self.feedback_path}'), {FEEDBACK_UI_PORT})"
                    ),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            # Give it a moment to start
            time.sleep(1.5)
            display.success(
                f"Feedback UI running at http://localhost:{FEEDBACK_UI_PORT}"
            )
            return proc
        except Exception as e:
            display.warning(f"Could not start feedback UI: {e}")
            return None

    def _stop_feedback_ui(self, proc: subprocess.Popen | None) -> None:
        """Gracefully stop the feedback UI subprocess."""
        if proc is None:
            return
        try:
            proc.send_signal(signal.SIGTERM)
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        display.info("Feedback UI stopped.")

    def _wait_for_feedback(self, round_num: int) -> list[str]:
        """Wait until the developer says feedback collection is done."""
        display.info("")
        display.info(
            "Testers can now submit feedback at "
            f"http://localhost:{FEEDBACK_UI_PORT}"
        )
        answer = display.prompt_user(
            "Press Enter when feedback collection is done (or 'skip' to skip):"
        )

        if answer.strip().lower() == "skip":
            return []

        # Read feedback from JSON file or API
        return self._read_collected_feedback()

    def _read_collected_feedback(self) -> list[str]:
        """Read feedback items from the JSON file written by the web UI."""
        if not self.feedback_path.exists():
            return []

        try:
            data = json.loads(self.feedback_path.read_text())
        except (json.JSONDecodeError, TypeError):
            return []

        # Handle both flat list of strings and list of dicts from the web UI
        items: list[str] = []
        if isinstance(data, list):
            for entry in data:
                if isinstance(entry, str):
                    items.append(entry)
                elif isinstance(entry, dict):
                    cat = entry.get("category", "general")
                    user = entry.get("user_name", "Anonymous")
                    text = entry.get("feedback", "")
                    if text:
                        items.append(f"[{cat}] ({user}): {text}")
                elif isinstance(entry, list):
                    # Nested format: [[round1_items], [round2_items]]
                    items.extend(str(e) for e in entry)

        return items

    def _incorporate_feedback(
        self, current_spec: str, feedback_items: list[str], round_num: int
    ) -> str:
        """Use the LLM to merge user feedback into the spec."""
        feedback_text = "\n".join(f"- {item}" for item in feedback_items)
        messages = [
            {
                "role": "system",
                "content": EXTERNAL_FEEDBACK_SYSTEM.format(round=round_num),
            },
            {
                "role": "user",
                "content": (
                    f"## Current Spec\n\n{current_spec}\n\n"
                    f"## User Feedback (Round {round_num})\n\n{feedback_text}"
                ),
            },
        ]
        response = self.client.chat(messages, temperature=0.3)
        return response.content
