import re
from dataclasses import dataclass
from pathlib import Path


class SpecError(Exception):
    pass


@dataclass(slots=True)
class SpecDocument:
    path: Path
    text: str

    @classmethod
    def load(cls, path: Path | str) -> "SpecDocument":
        path = Path(path)
        if not path.is_file():
            raise SpecError(f"Spec file not found: {path}")
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            raise SpecError(f"Spec file is empty: {path}")
        return cls(path=path, text=text)

    @classmethod
    def from_text(cls, text: str, *, title: str | None = None) -> "SpecDocument":
        text = text.strip()
        if not text:
            raise SpecError("Provided spec text is empty.")
        fallback = title or "composed-spec"
        return cls(path=Path(fallback), text=text)

    @property
    def title(self) -> str:
        match = re.search(r"^#\s+(.+)$", self.text, flags=re.MULTILINE)
        if match:
            return match.group(1).strip()
        return self.path.stem

    def language_hint(self) -> str | None:
        match = re.search(r"^\s*language\s*[:=]\s*([A-Za-z0-9_+#-]+)", self.text, flags=re.MULTILINE | re.IGNORECASE)
        if match:
            return match.group(1).lower()
        return None
