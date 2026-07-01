"""Loop 2 — Developer Feedback Loop.

The middle loop: developer reviews the built product → gives feedback →
feedback is merged into the spec → Loop 1 re-runs.
Runs on the order of *hours*.
"""

from __future__ import annotations

import subprocess
import sys
import signal
from pathlib import Path
from typing import Any

from loop_engineering.config import settings
from loop_engineering.ollama_client import OllamaClient
from loop_engineering.prompts import DEVELOPER_FEEDBACK_SYSTEM
from loop_engineering.loops.agentic import AgenticLoop
from loop_engineering import display
from loop_engineering.tracker import LoopTracker


class DeveloperLoop:
    """Loop 2: review → feedback → update spec → re-run Loop 1.

    Parameters
    ----------
    spec_path : Path | None
        Path to the product spec markdown file.
    workspace : Path | None
        Where generated code lives.
    max_rounds : int | None
        Max developer feedback rounds.
    """

    def __init__(
        self,
        spec_path: Path | None = None,
        workspace: Path | None = None,
        max_rounds: int | None = None,
        tracker: LoopTracker | None = None,
    ) -> None:
        self.spec_path = spec_path or settings.spec_path
        self.workspace = workspace or settings.workspace
        self.max_rounds = max_rounds or settings.max_developer_rounds
        self.client = OllamaClient()
        self.tracker = tracker or LoopTracker()

    def run(self) -> None:
        """Interactive developer feedback loop."""
        spec_text = self._read_spec()

        for round_num in range(1, self.max_rounds + 1):
            display.loop_header("developer", round_num)

            # ── Step 1: Run the agentic coding loop ────────────
            display.info("Running agentic coding loop with current spec...")
            agentic = AgenticLoop(
                spec_text=spec_text,
                workspace=self.workspace,
                tracker=self.tracker,
            )
            results = agentic.run()

            last = results[-1] if results else None
            if last and last.tests_passed:
                display.success("Agentic loop produced passing code.")
            else:
                display.warning("Agentic loop finished without all tests passing.")

            # ── Step 2: Optionally preview the app ─────────────
            self._offer_preview()

            # ── Step 3: Get developer feedback ─────────────────
            display.spec_preview(spec_text)
            feedback = display.prompt_user(
                "Review the app and enter feedback (or 'done' to finish, 'skip' to re-run):"
            )

            if feedback.strip().lower() in ("done", "quit", "exit", "q"):
                display.success(f"Developer loop complete after {round_num} round(s).")
                self.tracker.record(
                    loop="developer",
                    iteration=round_num,
                    success=True,
                    summary="Developer approved the product.",
                )
                break

            if feedback.strip().lower() == "skip":
                display.info("Skipping feedback — re-running agentic loop.")
                continue

            # ── Step 4: Update spec with feedback ──────────────
            display.info("Updating spec with developer feedback...")
            spec_text = self._update_spec(spec_text, feedback, round_num)
            self._write_spec(spec_text)
            display.success("Spec updated and saved.")

            self.tracker.record(
                loop="developer",
                iteration=round_num,
                success=True,
                summary=f"Feedback: {feedback[:80]}...",
            )
        else:
            display.warning(f"Reached max developer rounds ({self.max_rounds}).")

    # ── helpers ─────────────────────────────────────────────────

    def _read_spec(self) -> str:
        if self.spec_path.exists():
            return self.spec_path.read_text()
        display.error(f"Spec not found at {self.spec_path}. Run `loop-eng init` first.")
        raise SystemExit(1)

    def _write_spec(self, text: str) -> None:
        self.spec_path.write_text(text)

    def _update_spec(self, current_spec: str, feedback: str, round_num: int) -> str:
        """Ask the LLM to merge developer feedback into the spec."""
        messages = [
            {"role": "system", "content": DEVELOPER_FEEDBACK_SYSTEM.format(round=round_num)},
            {
                "role": "user",
                "content": (
                    f"## Current Spec\n\n{current_spec}\n\n"
                    f"## Developer Feedback\n\n{feedback}"
                ),
            },
        ]
        response = self.client.chat(messages, temperature=0.3)
        return response.content

    def _offer_preview(self) -> None:
        """Optionally launch the Flask app for the developer to preview."""
        app_file = self.workspace / "app.py"
        if not app_file.exists():
            return

        answer = display.prompt_user("Launch the Flask app for preview? (y/n)")
        if answer.strip().lower() not in ("y", "yes"):
            return

        display.info("Starting Flask app on http://localhost:5000 ...")
        display.info("Press Ctrl+C to stop the preview and return to feedback.")

        proc = subprocess.Popen(
            [sys.executable, str(app_file)],
            cwd=str(self.workspace),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            proc.wait()
        except KeyboardInterrupt:
            proc.send_signal(signal.SIGTERM)
            proc.wait(timeout=5)
            display.info("Flask app stopped.")
