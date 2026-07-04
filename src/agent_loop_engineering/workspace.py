import subprocess
from pathlib import Path

from .engines.base import CommandResult


class WorkspaceError(Exception):
    """Raised when an operation would escape or violate the workspace sandbox."""


class Workspace:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve(self, relpath: str | Path) -> Path:
        target = (self.root / relpath).resolve()
        # Ensure target is exactly root or has root in its parents
        if target != self.root and self.root not in target.parents:
            raise WorkspaceError(f"Path traversal attempt blocked: {relpath}")
        return target

    def relpath(self, path: str | Path) -> str:
        path_obj = Path(path)
        if path_obj.is_absolute():
            try:
                return str(path_obj.relative_to(self.root))
            except ValueError:
                return str(path_obj)
        return str(path_obj)

    def write_file(self, relpath: str | Path, content: str) -> Path:
        target = self.resolve(relpath)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def append_file(self, relpath: str | Path, content: str) -> Path:
        target = self.resolve(relpath)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as f:
            f.write(content)
        return target

    def read_file(self, relpath: str | Path) -> str:
        target = self.resolve(relpath)
        if not target.is_file():
            raise FileNotFoundError(f"No such file: {relpath}")
        return target.read_text(encoding="utf-8")

    def exists(self, relpath: str | Path) -> bool:
        target = self.resolve(relpath)
        return target.exists()

    def list_files(self) -> list[str]:
        # Sort relative paths
        paths = [p for p in self.root.rglob("*") if p.is_file()]
        return sorted([str(p.relative_to(self.root)) for p in paths])

    def run_command(self, command: str, *, timeout: float = 300.0) -> CommandResult:
        try:
            res = subprocess.run(
                command,
                shell=True,
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return CommandResult(
                command=command,
                exit_code=res.returncode,
                stdout=res.stdout,
                stderr=res.stderr,
                timed_out=False,
            )
        except subprocess.TimeoutExpired as e:
            stdout_data = e.stdout.decode('utf-8') if isinstance(e.stdout, bytes) else (e.stdout or "")
            stderr_data = e.stderr.decode('utf-8') if isinstance(e.stderr, bytes) else (e.stderr or "")
            note = f"\n[timed out after {timeout}s]"
            return CommandResult(
                command=command,
                exit_code=124,
                stdout=stdout_data,
                stderr=stderr_data + note,
                timed_out=True,
            )
