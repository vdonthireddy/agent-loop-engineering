import asyncio
import os
import re
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.markdown import Markdown

from .config import AppConfig
from .layered_spec import load_project, compose, LayeredSpecError
from .orchestrator import Orchestrator
from .spec import SpecDocument, SpecError
from .workspace import Workspace, WorkspaceError


def _load_dotenv(path=".env"):
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip()
                if v.startswith('"') and v.endswith('"'):
                    v = v[1:-1]
                elif v.startswith("'") and v.endswith("'"):
                    v = v[1:-1]
                if k not in os.environ:
                    os.environ[k] = v
    except FileNotFoundError:
        pass


@click.group()
@click.version_option(version="0.1.0")
def main():
    """Agent Loop Engineering CLI"""
    _load_dotenv()


def build_options(func):
    opts = [
        click.option("--out", "-o", "out_dir", help="Output directory (overrides default)"),
        click.option("--name", help="Project folder name"),
        click.option("--workspace", "workspace_dir", default="workspace", help="Root workspace directory"),
        click.option("--engine", help="Engine adapter"),
        click.option("--model", help="Model id"),
        click.option("--effort", help="Effort level"),
        click.option("--max-iterations", type=int, help="Max test-fix loops"),
        click.option("--max-design-iterations", type=int, help="Max design revise cycles"),
        click.option("--max-smoke-iterations", type=int, help="Max smoke fix cycles"),
        click.option("--max-test-review-iterations", type=int, help="Max test-review revise cycles"),
        click.option("--max-conformance-iterations", type=int, help="Max conformance fix cycles"),
        click.option("--language", help="Target language"),
        click.option("--test-command", help="Test runner command"),
        click.option("--design-review/--no-design-review", default=None, help="Run design gate"),
        click.option("--test-review/--no-test-review", default=None, help="Run test review loop"),
        click.option("--smoke-run/--no-smoke-run", default=None, help="Run smoke test"),
        click.option("--conformance/--no-conformance", default=None, help="Run conformance stage"),
        click.option("--verbose", is_flag=True, default=None, help="Write detailed transcript"),
        click.option("--dry-run", is_flag=True, default=None, help="Print plan but don't run LLM"),
        click.option("--debug", is_flag=True, default=None, help="Re-raise exceptions"),
        click.option("--strict-gate", is_flag=True, default=None, help="Strict unparseable gate"),
        click.option("--stop-after", type=click.Choice(["design", "code", "test", "smoke", "deploy", "conformance"]), help="Stop early"),
        click.option("--config-dir", default=".", help="Dir for .agentloop.toml"),
        click.option("--project-profile", help="Project config profile"),
    ]
    for opt in reversed(opts):
        func = opt(func)
    return func


def _effective_model(opts):
    model = opts.get("model")
    engine = opts.get("engine")
    if not model and engine == "azure":
        return os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")
    return model


def _resolve_config(opts, *, language=None, test_command=None):
    model = _effective_model(opts)
    
    # Bundle all overrides
    overrides = {
        "engine": opts.get("engine"),
        "model": model,
        "effort": opts.get("effort"),
        "language": language or opts.get("language"),
        "test_command": test_command or opts.get("test_command"),
        "max_iterations": opts.get("max_iterations"),
        "max_design_iterations": opts.get("max_design_iterations"),
        "max_smoke_iterations": opts.get("max_smoke_iterations"),
        "max_test_review_iterations": opts.get("max_test_review_iterations"),
        "max_conformance_iterations": opts.get("max_conformance_iterations"),
        "design_review": opts.get("design_review"),
        "test_review": opts.get("test_review"),
        "smoke_run": opts.get("smoke_run"),
        "conformance": opts.get("conformance"),
        "verbose": opts.get("verbose"),
        "dry_run": opts.get("dry_run"),
        "strict_gate": opts.get("strict_gate"),
        "stop_after": opts.get("stop_after")
    }
    # Drop Nones
    overrides = {k: v for k, v in overrides.items() if v is not None}
    
    return AppConfig.resolve(
        overrides=overrides,
        config_dir=opts.get("config_dir"),
        project=opts.get("project_profile")
    )


def _slug(text: str) -> str:
    s = re.sub(r'[^a-zA-Z0-9]+', '-', text).strip('-').lower()
    return s if s else "project"


def _resolve_out(opts, default_name: str) -> str:
    if opts.get("out_dir"):
        return opts["out_dir"]
    name = opts.get("name")
    if name:
        slugged = _slug(name)
    else:
        slugged = _slug(default_name)
    return str(Path(opts.get("workspace_dir", "workspace")) / slugged)


def _print_config(spec, config, out_dir):
    console = Console()
    console.print(f"[bold cyan]Agent Loop Engineering[/bold cyan] - Building: [green]{spec.title}[/green]")
    console.print(f"Target: [green]{out_dir}[/green]")
    console.print(f"Engine: [yellow]{config.engine}[/yellow], Model: [yellow]{config.model}[/yellow]")
    
    d_rev = f"on (max {config.max_design_iterations} cycles)" if config.design_review else "off"
    console.print(f"Design Review: [magenta]{d_rev}[/magenta]")
    
    s_run = f"on (max {config.max_smoke_iterations} fix cycles)" if config.smoke_run else "off"
    console.print(f"Smoke Run: [magenta]{s_run}[/magenta]")
    
    t_rev = f"on (max {config.max_test_review_iterations} cycles)" if config.test_review else "off"
    console.print(f"Test Review: [magenta]{t_rev}[/magenta]")
    
    c_rev = f"on (max {config.max_conformance_iterations} fix cycles)" if config.conformance else "off"
    console.print(f"Conformance: [magenta]{c_rev}[/magenta]")
    
    if config.engine == "local":
        base_url = os.environ.get("AGENTLOOP_BASE_URL", "http://localhost:11434/v1")
        console.print(f"Local Base URL: {base_url}")
        if config.model and config.model.startswith("claude"):
            console.print("[bold red]WARNING: Engine is local but model is claude. This may fail if the local server doesn't support this model name.[/bold red]")


def _run_build(spec, config, out_dir, debug):
    _print_config(spec, config, out_dir)
    if config.dry_run:
        return
        
    console = Console()
    try:
        ws = Workspace(out_dir)
        orchestrator = Orchestrator(
            config,
            progress=lambda stage, msg: console.print(f"[[blue]{stage}[/blue]] {msg}"),
            run_log=str(ws.resolve("run.log")) if getattr(config, "run_log", True) else None
        )
        report = asyncio.run(orchestrator.build(spec, ws))
        
        console.print("\n" + "=" * 50 + "\n")
        
        status = "[bold green]SUCCESS[/bold green]" if report.ok else "[bold red]INCOMPLETE[/bold red]"
        console.print(f"Build Result: {status}")
        
        if config.design_review:
            if report.stopped_at_design_gate:
                console.print("[bold red]Build stopped at the design gate — no code was generated.[/bold red]")
            else:
                appr = "yes" if report.design_approved else "no"
                console.print(f"Design Approved: {appr} (in {report.design_iterations} cycles)")
                
        console.print(f"Tests Passed: {'yes' if report.tests_passed else 'no'} (in {getattr(report, 'iterations_used', 0)} cycles)")
        
        if config.smoke_run and report.smoke_passed is not None:
            console.print(f"Smoke Run (app starts): {'yes' if report.smoke_passed else 'no'} (in {report.smoke_iterations} cycles)")
            
        if config.conformance and report.conformant is not None:
            console.print(f"Conformant: {'yes' if report.conformant else 'no'} (in {report.conformance_iterations} cycles)")
            
        console.print(f"\nReport written to: [blue]{out_dir}/report.md[/blue]")
        
        if not report.ok:
            sys.exit(1)
            
    except Exception as e:
        if debug:
            raise
        console.print(f"[bold red]{type(e).__name__}:[/bold red] {e}")
        sys.exit(1)


@main.command()
@click.argument("spec_path", type=click.Path(exists=True))
@build_options
def build(spec_path, **opts):
    """Build a project from a single specification file."""
    try:
        path_obj = Path(spec_path)
        spec = SpecDocument.load(path_obj)
    except SpecError as e:
        click.echo(f"Spec error: {e}", err=True)
        sys.exit(2)
        
    if path_obj.name in ("spec.md", "brd.md"):
        default_name = path_obj.parent.name
    else:
        default_name = path_obj.stem
        
    out_dir = _resolve_out(opts, default_name)
    config = _resolve_config(opts, language=spec.language_hint())
    
    _run_build(spec, config, out_dir, opts.get("debug"))


@main.command("build-project")
@click.argument("project_dir", type=click.Path(exists=True, file_okay=False))
@build_options
def build_project(project_dir, **opts):
    """Compose a layered project and build it."""
    try:
        project = load_project(Path(project_dir))
        composed = compose(project)
        spec = SpecDocument.from_text(composed.text, title=composed.title)
    except LayeredSpecError as e:
        click.echo(f"Layered spec error: {e}", err=True)
        sys.exit(2)
        
    default_name = Path(project_dir).name
    out_dir = _resolve_out(opts, default_name)
    
    config = _resolve_config(
        opts, 
        language=opts.get("language") or composed.language,
        test_command=opts.get("test_command") or composed.test_command
    )
    
    _run_build(spec, config, out_dir, opts.get("debug"))


@click.command(name="compose")
@click.argument("project_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--out", "-o", "out_path", type=click.Path(), help="File to write composed spec to")
def compose_cmd(project_dir, out_path):
    """Render the effective spec from a layered project (no LLM calls)."""
    try:
        project = load_project(Path(project_dir))
        composed = compose(project)
    except LayeredSpecError as e:
        click.echo(f"Layered spec error: {e}", err=True)
        sys.exit(2)
        
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(composed.text)
    else:
        click.echo(composed.text)

main.add_command(compose_cmd)

if __name__ == "__main__":
    main()
