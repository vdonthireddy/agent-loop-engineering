"""CLI entry point — `loop-eng` command."""

from __future__ import annotations

from pathlib import Path

import click

from loop_engineering.config import settings
from loop_engineering import display
from loop_engineering.tracker import LoopTracker

# ── Default spec content ────────────────────────────────────────

DEFAULT_SPEC = """\
# To-Do App — Product Specification

## Overview
A minimal but functional to-do list web application built with Flask and SQLite.

## Core Features

### 1. Task Management (CRUD)
- **Add a task:** User enters a title via a form and submits it.
- **List tasks:** All tasks are displayed on the main page, showing title and status.
- **Complete a task:** User can mark a task as done (toggle).
- **Delete a task:** User can remove a task permanently.

### 2. Data Storage
- Use Python's built-in `sqlite3` module (no ORM).
- Database file: `todo.db` in the app's working directory.
- Schema: `tasks` table with columns `id` (INTEGER PRIMARY KEY), `title` (TEXT NOT NULL), `done` (BOOLEAN DEFAULT 0).

### 3. Web Interface
- Single-page UI rendered with Jinja2 templates.
- HTML form at the top for adding new tasks.
- Task list below with checkboxes for completion and delete buttons.
- Minimal inline CSS for readability (no external frameworks required).

### 4. Routes
| Route | Method | Action |
|---|---|---|
| `/` | GET | Show all tasks |
| `/add` | POST | Add a new task |
| `/complete/<id>` | POST | Toggle task completion |
| `/delete/<id>` | POST | Delete a task |

### 5. Testing
- Write pytest tests in `tests/test_app.py`.
- Tests should use Flask's test client (no real server needed).
- Cover: adding a task, listing tasks, completing a task, deleting a task.
- Use a temporary database for each test (not the production `todo.db`).

## Constraints
- Python 3.10+
- Flask (latest stable)
- No external CSS/JS frameworks
- All code in a single `app.py` plus `templates/` and `tests/`
"""


@click.group()
def main() -> None:
    """loop-eng — 3 Key Product Development Loops, demonstrated end-to-end."""
    pass


@main.command()
def init() -> None:
    """Create the initial product spec and workspace."""
    # Write spec
    if settings.spec_path.exists():
        overwrite = display.prompt_user(
            f"Spec already exists at {settings.spec_path}. Overwrite? (y/n)"
        )
        if overwrite.strip().lower() not in ("y", "yes"):
            display.info("Keeping existing spec.")
            return

    settings.spec_path.write_text(DEFAULT_SPEC)
    display.success(f"Spec written to {settings.spec_path}")

    # Create workspace
    settings.workspace.mkdir(parents=True, exist_ok=True)
    display.success(f"Workspace created at {settings.workspace}")

    # Reset history
    tracker = LoopTracker()
    tracker.entries = []
    tracker._save()
    display.success(f"Loop history reset at {settings.history_path}")

    display.info("Run `loop-eng code` to start the agentic coding loop.")


@main.command()
def code() -> None:
    """Run Loop 1 only — agentic coding (spec → code → test → fix)."""
    from loop_engineering.loops.agentic import AgenticLoop
    from loop_engineering.ollama_client import OllamaClient

    _check_prereqs()

    spec_text = settings.spec_path.read_text()
    display.spec_preview(spec_text)

    tracker = LoopTracker()
    loop = AgenticLoop(spec_text=spec_text, tracker=tracker)
    results = loop.run()

    display.summary_table(tracker.all())

    # Report final state
    if results and results[-1].tests_passed:
        display.success("Agentic coding loop completed successfully!")
        display.info(f"Generated app is in {settings.workspace}")
    else:
        display.warning("Agentic coding loop finished without all tests passing.")


@main.command()
def dev() -> None:
    """Run Loop 1 + Loop 2 — coding + developer feedback."""
    from loop_engineering.loops.developer import DeveloperLoop

    _check_prereqs()

    tracker = LoopTracker()
    loop = DeveloperLoop(tracker=tracker)
    loop.run()

    display.summary_table(tracker.all())


@main.command()
def full() -> None:
    """Run all 3 loops end-to-end — the complete loop engineering demo."""
    from loop_engineering.loops.external import ExternalLoop

    _check_prereqs()

    # Check for optional feedback.json
    feedback_path = settings.workspace.parent / "feedback.json"
    fp = feedback_path if feedback_path.exists() else None

    tracker = LoopTracker()
    loop = ExternalLoop(feedback_path=fp, tracker=tracker)
    loop.run()


@main.command()
def status() -> None:
    """Show the current state — spec, iterations, test results."""
    display.console.rule("[bold cyan]📊 Loop Engineering Status[/]")

    # Spec
    if settings.spec_path.exists():
        spec_text = settings.spec_path.read_text()
        line_count = len(spec_text.splitlines())
        display.info(f"Spec: {settings.spec_path} ({line_count} lines)")
    else:
        display.warning(f"No spec found at {settings.spec_path}. Run `loop-eng init`.")

    # Workspace
    if settings.workspace.exists():
        files = list(settings.workspace.rglob("*"))
        file_count = sum(1 for f in files if f.is_file())
        display.info(f"Workspace: {settings.workspace} ({file_count} files)")
    else:
        display.info("Workspace: not created yet.")

    # History
    tracker = LoopTracker()
    if tracker.entries:
        display.info(f"Total iterations: {tracker.count()}")
        display.info(f"  Agentic:   {tracker.count('agentic')}")
        display.info(f"  Developer: {tracker.count('developer')}")
        display.info(f"  External:  {tracker.count('external')}")
        display.summary_table(tracker.all())
    else:
        display.info("No loop history yet.")

    # Ollama
    from loop_engineering.ollama_client import OllamaClient

    client = OllamaClient()
    if client.is_available():
        display.success(f"Ollama is running at {settings.ollama_url}")
        if client.has_model():
            display.success(f"Model '{settings.model}' is available.")
        else:
            display.warning(f"Model '{settings.model}' not found. Run: ollama pull {settings.model}")
    else:
        display.error(f"Ollama not reachable at {settings.ollama_url}")


@main.command()
@click.option("--port", default=5001, help="Port for the feedback web UI")
def feedback(port: int) -> None:
    """Launch the feedback web UI for external testers."""
    from loop_engineering.feedback_ui import run_feedback_server

    feedback_path = settings.workspace.parent / "feedback.json"
    display.console.rule("[bold yellow]🟠 External Feedback Portal[/]")
    display.info(f"Feedback will be saved to {feedback_path}")
    display.info(f"Starting web UI at http://localhost:{port}")
    display.info("Press Ctrl+C to stop.\n")

    try:
        run_feedback_server(feedback_path, port=port)
    except KeyboardInterrupt:
        display.info("Feedback server stopped.")


# ── helpers ─────────────────────────────────────────────────────


def _check_prereqs() -> None:
    """Validate that Ollama is running and spec exists."""
    from loop_engineering.ollama_client import OllamaClient

    # Check spec
    if not settings.spec_path.exists():
        display.error(f"Spec not found at {settings.spec_path}")
        display.info("Run `loop-eng init` first to create the initial spec.")
        raise SystemExit(1)

    # Check Ollama
    client = OllamaClient()
    if not client.is_available():
        display.error(f"Ollama is not running at {settings.ollama_url}")
        display.info("Start Ollama with: ollama serve")
        raise SystemExit(1)

    if not client.has_model():
        display.warning(f"Model '{settings.model}' not found locally.")
        display.info(f"Pull it with: ollama pull {settings.model}")
        display.info("Or set LOOP_ENG_MODEL to a model you already have.")
        raise SystemExit(1)

    display.success(f"Ollama ready — model: {settings.model}")


if __name__ == "__main__":
    main()

