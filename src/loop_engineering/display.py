"""Rich console output for the loop engineering demo."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.markdown import Markdown
from rich import box

console = Console()

# ── Loop color scheme ───────────────────────────────────────────

LOOP_STYLES = {
    "agentic":   {"emoji": "🔵", "color": "bright_blue",  "label": "Agentic Coding Loop"},
    "developer": {"emoji": "🟢", "color": "bright_green", "label": "Developer Feedback Loop"},
    "external":  {"emoji": "🟠", "color": "bright_yellow","label": "External Feedback Loop"},
}


def loop_header(loop_name: str, iteration: int, detail: str = "") -> None:
    """Print a prominent header for a loop iteration."""
    style = LOOP_STYLES.get(loop_name, LOOP_STYLES["agentic"])
    title = f"{style['emoji']}  {style['label']}  —  Iteration {iteration}"
    if detail:
        title += f"  ({detail})"
    console.print()
    console.rule(f"[bold {style['color']}]{title}[/]", style=style["color"])
    console.print()


def loop_result(loop_name: str, iteration: int, success: bool, summary: str) -> None:
    """Print a result box after a loop iteration."""
    style = LOOP_STYLES.get(loop_name, LOOP_STYLES["agentic"])
    status = "[bold green]✅ PASS[/]" if success else "[bold red]❌ FAIL[/]"
    panel = Panel(
        f"{status}\n\n{summary}",
        title=f"{style['emoji']} {style['label']} — Iteration {iteration}",
        border_style=style["color"],
        padding=(1, 2),
    )
    console.print(panel)


def files_written(file_paths: list[str]) -> None:
    """Display a table of files the agent wrote."""
    table = Table(
        title="📄 Files Written",
        box=box.ROUNDED,
        show_lines=False,
        header_style="bold cyan",
    )
    table.add_column("File", style="white")
    for fp in sorted(file_paths):
        table.add_row(fp)
    console.print(table)


def test_results_panel(output: str, passed: bool) -> None:
    """Show test output in a panel."""
    border = "green" if passed else "red"
    title = "🧪 Test Results — PASS" if passed else "🧪 Test Results — FAIL"
    console.print(Panel(output[-2000:], title=title, border_style=border, padding=(0, 1)))


def spec_preview(spec_text: str) -> None:
    """Render the current spec as markdown."""
    console.print(Panel(Markdown(spec_text[:3000]), title="📋 Current Spec", border_style="cyan"))


def info(msg: str) -> None:
    console.print(f"  [dim]ℹ {msg}[/]")


def success(msg: str) -> None:
    console.print(f"  [bold green]✅ {msg}[/]")


def warning(msg: str) -> None:
    console.print(f"  [bold yellow]⚠️  {msg}[/]")


def error(msg: str) -> None:
    console.print(f"  [bold red]❌ {msg}[/]")


def prompt_user(message: str) -> str:
    """Prompt the user for input with rich formatting."""
    console.print(f"\n[bold cyan]💬 {message}[/]")
    return console.input("[dim]> [/]")


def summary_table(history: list[dict]) -> None:
    """Print a summary table of all loop iterations."""
    table = Table(
        title="📊 Loop Engineering — Session Summary",
        box=box.DOUBLE_EDGE,
        header_style="bold magenta",
    )
    table.add_column("#", style="dim", width=4)
    table.add_column("Loop", width=22)
    table.add_column("Iteration", justify="center", width=10)
    table.add_column("Result", justify="center", width=8)
    table.add_column("Detail", max_width=50)

    for i, entry in enumerate(history, 1):
        style = LOOP_STYLES.get(entry.get("loop", "agentic"), LOOP_STYLES["agentic"])
        result = "✅" if entry.get("success") else "❌"
        table.add_row(
            str(i),
            f"{style['emoji']} {style['label']}",
            str(entry.get("iteration", "?")),
            result,
            entry.get("summary", "")[:50],
        )

    console.print()
    console.print(table)
    console.print()
