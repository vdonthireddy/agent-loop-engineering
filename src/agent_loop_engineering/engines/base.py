from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(slots=True)
class ToolCall:
    name: str
    summary: str
    ok: bool = True


@dataclass(slots=True)
class CommandResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out

    @property
    def combined_output(self) -> str:
        out = self.stdout.strip()
        err = self.stderr.strip()
        if out and err:
            return f"{out}\n{err}"
        return out or err


@dataclass(slots=True)
class AgentResult:
    text: str
    files_touched: list[str] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = "end_turn"


@runtime_checkable
class Engine(Protocol):
    name: str

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
        """
        Run the agent. Implementations MUST confine all file/command access to `workspace`.
        """
        ...
