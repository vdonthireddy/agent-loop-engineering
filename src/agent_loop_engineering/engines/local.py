import os
from collections.abc import Sequence
from pathlib import Path

from ._openai_common import run_openai_tool_loop
from .base import AgentResult

_DEFAULT_BASE_URL = "http://localhost:11434/v1"


class LocalEngine:
    name = "local"

    def __init__(self):
        try:
            import openai
        except ImportError:
            raise RuntimeError("The 'openai' package is required for the local engine. Run pip install openai.")

        self.base_url = os.environ.get("AGENTLOOP_BASE_URL", _DEFAULT_BASE_URL)
        self.api_key = os.environ.get("AGENTLOOP_API_KEY", "ollama")

    async def run_agent(
        self,
        *,
        system_prompt: str,
        task: str,
        workspace: Path,
        tools: Sequence[str],
        model: str,
        effort: str,
    ) -> AgentResult:
        from openai import AsyncOpenAI
        
        client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
        )

        return await run_openai_tool_loop(
            client=client,
            model=model,
            system_prompt=system_prompt,
            task=task,
            workspace=workspace,
        )
