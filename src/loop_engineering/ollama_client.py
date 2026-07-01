"""Thin wrapper around the Ollama REST API (/api/chat)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import requests

from loop_engineering.config import settings


@dataclass
class OllamaResponse:
    """Parsed response from Ollama."""

    content: str = ""
    model: str = ""
    total_duration_ns: int = 0

    @property
    def duration_seconds(self) -> float:
        return self.total_duration_ns / 1e9


class OllamaClient:
    """Stateless client — each call sends the full conversation history."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self.base_url = (base_url or settings.ollama_url).rstrip("/")
        self.model = model or settings.model

    # ── public API ──────────────────────────────────────────────

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.2,
        stream: bool = False,
    ) -> OllamaResponse:
        """Send a chat-completion request and return the full response.

        Parameters
        ----------
        messages : list of {"role": ..., "content": ...} dicts
        temperature : sampling temperature (low = more deterministic)
        stream : if True, prints tokens as they arrive (still returns full text)
        """
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "options": {"temperature": temperature},
        }

        url = f"{self.base_url}/api/chat"

        if not stream:
            resp = requests.post(url, json=payload, timeout=300)
            resp.raise_for_status()
            data = resp.json()
            return OllamaResponse(
                content=data.get("message", {}).get("content", ""),
                model=data.get("model", self.model),
                total_duration_ns=data.get("total_duration", 0),
            )

        # Streaming mode — collect tokens, optionally print live
        collected: list[str] = []
        model_name = self.model
        total_dur = 0

        resp = requests.post(url, json=payload, timeout=300, stream=True)
        resp.raise_for_status()

        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            chunk = json.loads(line)
            token = chunk.get("message", {}).get("content", "")
            collected.append(token)
            if chunk.get("done"):
                model_name = chunk.get("model", model_name)
                total_dur = chunk.get("total_duration", 0)

        return OllamaResponse(
            content="".join(collected),
            model=model_name,
            total_duration_ns=total_dur,
        )

    def is_available(self) -> bool:
        """Check whether the Ollama server is reachable."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except requests.ConnectionError:
            return False

    def has_model(self) -> bool:
        """Check whether the configured model is pulled locally."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
            # Ollama may store as "qwen2.5-coder:7b" or "qwen2.5-coder:7b-instruct"
            return any(self.model in m or m.startswith(self.model) for m in models)
        except Exception:
            return False
