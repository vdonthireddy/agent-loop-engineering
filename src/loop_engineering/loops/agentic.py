"""Loop 1 — Agentic Coding Loop.

The inner loop: spec → LLM generates code → run tests → fix on failure → repeat.
Runs on the order of *minutes*.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loop_engineering.config import settings
from loop_engineering.ollama_client import OllamaClient
from loop_engineering.prompts import CODING_AGENT_SYSTEM, CODING_AGENT_FIX
from loop_engineering import display
from loop_engineering.tracker import LoopTracker


@dataclass
class IterationResult:
    """Outcome of a single code-test-fix iteration."""

    iteration: int
    files_written: list[str] = field(default_factory=list)
    tests_passed: bool = False
    test_output: str = ""
    llm_duration_s: float = 0.0


# ── helpers ─────────────────────────────────────────────────────


def extract_files(llm_output: str) -> dict[str, str]:
    """Parse fenced code blocks from LLM output into {path: content}.

    Handles many formats that LLMs produce:
        ```path: app.py           ← explicit path header
        ```python app.py          ← language + filename
        ```python                 ← language-only (filename inferred)
        # app.py                  ← comment at top of block
        **app.py**                ← bold filename before block
        `app.py`:                 ← inline code filename before block
    """
    files: dict[str, str] = {}

    # Find all fenced code blocks (triple backtick)
    block_re = re.compile(r"```(\w*[^\n]*)\n(.*?)```", re.DOTALL)

    # Pre-scan for filename hints right before code blocks
    filename_hint_re = re.compile(
        r"(?:\*\*|`)([\w/.]+\.(?:py|html|css|js|json|txt|md|toml|cfg|ini|yaml|yml))(?:\*\*|`|:)",
    )

    # Track assigned default names to avoid collisions
    lang_counters: dict[str, int] = {}
    DEFAULT_FILENAMES = {
        "python": "app.py",
        "html": "templates/index.html",
        "jinja2": "templates/index.html",
        "jinja": "templates/index.html",
        "css": "static/style.css",
        "javascript": "static/script.js",
        "js": "static/script.js",
        "json": "config.json",
        "bash": "run.sh",
        "sh": "run.sh",
    }

    for match in block_re.finditer(llm_output):
        info_string = match.group(1).strip()
        content = match.group(2)
        filename: str | None = None

        # ── Strategy 1: "path: filename" in the info string ──
        path_match = re.search(r"path:\s*(\S+)", info_string, re.IGNORECASE)
        if path_match:
            filename = path_match.group(1).strip().strip("`\"'")

        # ── Strategy 2: language + filename in info string ──
        if not filename:
            parts = info_string.split()
            if len(parts) >= 2:
                candidate = parts[-1].strip().strip("`\"'")
                if "." in candidate and not candidate.startswith("#"):
                    filename = candidate

        # ── Strategy 3: Filename in a comment at the top of the block ──
        if not filename:
            first_lines = content.strip().split("\n", 3)
            for line in first_lines[:2]:
                line_stripped = line.strip()
                # Python: # app.py or # File: app.py
                comment_match = re.match(
                    r"^#\s*(?:File:\s*|file:\s*)?([\w/.]+\.(?:py|html|css|js|json|txt|toml))\s*$",
                    line_stripped,
                )
                if comment_match:
                    filename = comment_match.group(1)
                    break
                # HTML: <!-- templates/index.html -->
                html_comment = re.match(
                    r"^<!--\s*([\w/.]+\.(?:html|css|js))\s*-->$",
                    line_stripped,
                )
                if html_comment:
                    filename = html_comment.group(1)
                    break

        # ── Strategy 4: Bold/inline-code filename before the block ──
        if not filename:
            block_start = match.start()
            preceding = llm_output[max(0, block_start - 200):block_start]
            hints = list(filename_hint_re.finditer(preceding))
            if hints:
                filename = hints[-1].group(1)

        # ── Strategy 5: Infer from language tag ──
        if not filename:
            lang = info_string.split()[0].lower() if info_string else ""
            if lang in DEFAULT_FILENAMES:
                base = DEFAULT_FILENAMES[lang]
                count = lang_counters.get(lang, 0)
                lang_counters[lang] = count + 1
                if count == 0:
                    filename = base
                elif lang == "python":
                    if "test" in content.lower() or "pytest" in content.lower():
                        filename = "tests/test_app.py"
                    else:
                        filename = f"module_{count}.py"
                elif lang in ("html", "jinja2", "jinja"):
                    filename = f"templates/page_{count}.html"
                else:
                    name, ext = base.rsplit(".", 1)
                    filename = f"{name}_{count}.{ext}"

        # ── Final: skip blocks with no identifiable filename ──
        if not filename:
            continue

        # Clean up the filename
        filename = filename.strip("/").strip()
        if filename.startswith("./"):
            filename = filename[2:]

        files[filename] = content

    return files



def write_files(workspace: Path, files: dict[str, str]) -> list[str]:
    """Write extracted files into the workspace directory."""
    written: list[str] = []
    for rel_path, content in files.items():
        target = workspace / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        written.append(rel_path)
    return written


def run_tests(workspace: Path) -> tuple[bool, str]:
    """Run pytest in the workspace. Returns (passed, output)."""
    test_dir = workspace / "tests"
    if not test_dir.exists():
        return False, "No tests/ directory found in workspace."

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=short", str(test_dir)],
        cwd=str(workspace),
        capture_output=True,
        text=True,
        timeout=60,
        env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    output = result.stdout + result.stderr
    passed = result.returncode == 0
    return passed, output


# ── main loop ───────────────────────────────────────────────────


class AgenticLoop:
    """Loop 1: spec → code → test → fix → repeat.

    Parameters
    ----------
    spec_text : str
        The current product specification (markdown).
    workspace : Path | None
        Directory where generated code is written.
    max_iterations : int
        Safety cap on code-test-fix cycles.
    """

    def __init__(
        self,
        spec_text: str,
        workspace: Path | None = None,
        max_iterations: int | None = None,
        tracker: LoopTracker | None = None,
    ) -> None:
        self.spec_text = spec_text
        self.workspace = workspace or settings.workspace
        self.max_iterations = max_iterations or settings.max_agentic_iterations
        self.client = OllamaClient()
        self.tracker = tracker or LoopTracker()

    def run(self) -> list[IterationResult]:
        """Execute the agentic coding loop. Returns results per iteration."""
        self.workspace.mkdir(parents=True, exist_ok=True)

        results: list[IterationResult] = []
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": CODING_AGENT_SYSTEM},
            {"role": "user", "content": f"## Product Specification\n\n{self.spec_text}"},
        ]

        for i in range(1, self.max_iterations + 1):
            display.loop_header("agentic", i, f"max {self.max_iterations}")

            # ── Step 1: Ask LLM to generate / fix code ─────────
            display.info("Calling Ollama for code generation...")
            response = self.client.chat(messages, temperature=0.2)
            display.info(f"LLM responded in {response.duration_seconds:.1f}s")

            # ── Step 2: Extract files from response ────────────
            files = extract_files(response.content)
            if not files:
                display.warning("No code blocks extracted from LLM output. Retrying...")
                # Feed the raw output back so the LLM can try again
                messages.append({"role": "assistant", "content": response.content})
                messages.append({
                    "role": "user",
                    "content": (
                        "I could not find any code blocks in your response. "
                        "Please output ALL files using fenced code blocks with "
                        "path headers like:\n```path: app.py\n<code>\n```"
                    ),
                })
                results.append(IterationResult(iteration=i, llm_duration_s=response.duration_seconds))
                continue

            written = write_files(self.workspace, files)
            display.files_written(written)

            # ── Step 3: Run tests ──────────────────────────────
            display.info("Running tests...")
            passed, test_output = run_tests(self.workspace)
            display.test_results_panel(test_output, passed)

            result = IterationResult(
                iteration=i,
                files_written=written,
                tests_passed=passed,
                test_output=test_output,
                llm_duration_s=response.duration_seconds,
            )
            results.append(result)

            # Track it
            self.tracker.record(
                loop="agentic",
                iteration=i,
                success=passed,
                summary=f"{'PASS' if passed else 'FAIL'} — {len(written)} files written",
                extra={"files": written},
            )

            if passed:
                display.loop_result(
                    "agentic", i, True,
                    f"All tests pass after {i} iteration(s). "
                    f"Files: {', '.join(written)}",
                )
                break

            # ── Step 4: Feed errors back to LLM ───────────────
            display.info("Tests failed — feeding errors back to the agent...")
            messages.append({"role": "assistant", "content": response.content})
            messages.append({
                "role": "user",
                "content": CODING_AGENT_FIX.format(test_output=test_output),
            })
        else:
            display.loop_result(
                "agentic", self.max_iterations, False,
                f"Reached max iterations ({self.max_iterations}) without all tests passing.",
            )

        return results
