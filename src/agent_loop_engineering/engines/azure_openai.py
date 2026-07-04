import os
from collections.abc import Sequence
from pathlib import Path

from ._openai_common import run_openai_tool_loop
from .base import AgentResult


class AzureOpenAIEngine:
    name = "azure"

    def __init__(self):
        try:
            import openai
        except ImportError:
            raise RuntimeError("The 'openai' package is required for the azure engine. Run pip install openai.")

        self.endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT") or os.environ.get("ENDPOINT_URL")
        self.api_key = os.environ.get("AZURE_OPENAI_API_KEY")
        self.api_version = os.environ.get("AZURE_OPENAI_API_VERSION") or os.environ.get("OPENAI_API_VERSION")
        self.deployment_name = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")

        missing = []
        if not self.endpoint: missing.append("AZURE_OPENAI_ENDPOINT")
        if not self.api_key: missing.append("AZURE_OPENAI_API_KEY")
        if not self.api_version: missing.append("AZURE_OPENAI_API_VERSION")
        if not self.deployment_name: missing.append("AZURE_OPENAI_DEPLOYMENT_NAME")

        if missing:
            raise RuntimeError(f"Missing required Azure environment variables: {', '.join(missing)}")

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
        from openai import AsyncAzureOpenAI
        
        client = AsyncAzureOpenAI(
            azure_endpoint=self.endpoint,
            api_key=self.api_key,
            api_version=self.api_version,
        )

        # Fallback to default deployment name if model is not explicitly set or is a claude default
        actual_model = model
        if not model or model.startswith("claude"):
            actual_model = self.deployment_name

        return await run_openai_tool_loop(
            client=client,
            model=actual_model,
            system_prompt=system_prompt,
            task=task,
            workspace=workspace,
        )
