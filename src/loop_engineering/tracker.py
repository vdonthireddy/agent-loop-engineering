"""Track the history of all loop iterations — persisted to JSON."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loop_engineering.config import settings


class LoopTracker:
    """Append-only log of every loop iteration, persisted to disk."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or settings.history_path
        self.entries: list[dict[str, Any]] = []
        self._load()

    # ── public ──────────────────────────────────────────────────

    def record(
        self,
        loop: str,
        iteration: int,
        success: bool,
        summary: str,
        *,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Record a loop iteration result."""
        entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "loop": loop,
            "iteration": iteration,
            "success": success,
            "summary": summary,
        }
        if extra:
            entry["extra"] = extra
        self.entries.append(entry)
        self._save()

    def latest(self, loop: str | None = None) -> dict[str, Any] | None:
        """Return the most recent entry, optionally filtered by loop name."""
        filtered = self.entries if loop is None else [e for e in self.entries if e["loop"] == loop]
        return filtered[-1] if filtered else None

    def count(self, loop: str | None = None) -> int:
        if loop is None:
            return len(self.entries)
        return sum(1 for e in self.entries if e["loop"] == loop)

    def all(self) -> list[dict[str, Any]]:
        return list(self.entries)

    # ── persistence ─────────────────────────────────────────────

    def _load(self) -> None:
        if self.path.exists():
            try:
                self.entries = json.loads(self.path.read_text())
            except (json.JSONDecodeError, TypeError):
                self.entries = []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.entries, indent=2) + "\n")
