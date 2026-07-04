from collections.abc import Sequence
from pathlib import Path

from ..workspace import Workspace
from .base import AgentResult, ToolCall


_TOOL_NAME_MAP = {
    "run_bash": "Bash",
    "bash": "Bash",
    "read_file": "Read",
    "write_file": "Write",
    "str_replace": "Edit",
    "list_files": "Glob",
    "grep": "Grep",
}

class AgentSDKEngine:
    name = "agent_sdk"

    def __init__(self):
        try:
            import claude_agent_sdk
        except ImportError:
            raise RuntimeError("The 'claude-agent-sdk' package is required. Run pip install claude-agent-sdk.")

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
        from claude_agent_sdk import ClaudeAgentOptions, query
        from claude_agent_sdk.messages import AssistantMessage, ToolUseBlock, ResultMessage

        allowed = [_TOOL_NAME_MAP.get(t, t) for t in tools]
        
        opts = ClaudeAgentOptions(
            system_prompt=system_prompt,
            allowed_tools=allowed,
            cwd=str(workspace.resolve()),
            model=model,
            permission_mode="acceptEdits"
        )
        
        files_touched = []
        tool_calls_log = []
        texts = []
        stop_reason = "end_turn"
        
        ws = Workspace(workspace)
        
        try:
            async for msg in query(prompt=task, options=opts):
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if block.type == "text":
                            texts.append(block.text)
                        elif isinstance(block, ToolUseBlock):
                            tool_calls_log.append(ToolCall(
                                name=block.name,
                                summary=self._summarize(block),
                                ok=True  # Simplified, actual result comes in ResultMessage
                            ))
                            tp = self._touched_path(block)
                            if tp:
                                files_touched.append(ws.relpath(tp))
                                
                elif isinstance(msg, ResultMessage):
                    if hasattr(msg, 'subtype'):
                        stop_reason = msg.subtype
        except Exception as e:
            texts.append(f"SDK Error: {e}")
            stop_reason = "error"

        return AgentResult(
            text="".join(texts),
            files_touched=sorted(list(set(files_touched))),
            tool_calls=tool_calls_log,
            stop_reason=stop_reason
        )

    def _summarize(self, block) -> str:
        if block.name == "Bash":
            cmd = block.input.get("command", "")
            return f"Bash: {cmd[:40]}"
        return f"called {block.name}"

    def _touched_path(self, block) -> str | None:
        if block.name in ("Write", "Edit"):
            return block.input.get("path")
        return None
