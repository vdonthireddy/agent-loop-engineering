import string
from functools import lru_cache
from pathlib import Path

VERDICT_JSON_NUDGE = "verdict_json_nudge"
SMOKE_WRITE_NUDGE = "smoke_write_nudge"


@lru_cache(maxsize=None)
def _load_cached(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load(name: str, extra_dir: str | Path | None = None) -> str:
    if extra_dir:
        extra_path = Path(extra_dir) / "prompts" / f"{name}.md"
        if extra_path.is_file():
            return _load_cached(extra_path)

    pkg_path = Path(__file__).parent / "prompts" / f"{name}.md"
    if pkg_path.is_file():
        return _load_cached(pkg_path)
        
    raise FileNotFoundError(f"Prompt '{name}.md' not found.")


def render(name: str, extra_dir: str | Path | None = None, **vars) -> str:
    text = load(name, extra_dir)
    return string.Template(text).safe_substitute(vars)


def render_string(text: str, **vars) -> str:
    import string
    return string.Template(text).safe_substitute(vars)
