import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import AppConfig
from .engines.base import AgentResult, Engine
from . import prompts
from .spec import SpecDocument
from .workspace import Workspace


@dataclass(slots=True)
class AgentContext:
    engine: Engine
    config: AppConfig
    workspace: Workspace
    spec: SpecDocument
    global_spec: str = ""
    notes: dict = field(default_factory=dict)
    
    def global_section(self) -> str:
        if self.global_spec:
            return f"\n\n## Global Requirements & Stack\n{self.global_spec}"
        return ""


@dataclass(slots=True)
class AgentSpec:
    role: str
    prompt: str
    task: str
    tools: list[str]
    extra_dir: str | None


@dataclass(slots=True)
class GateSpec:
    stage: str
    placement: str
    generator: str | None
    critic: str
    reviser: str | None
    verdict_file: str
    verdict_key: str
    max_iterations: int
    blocking: bool


def load_registry(agent_defs_dir: str | None = None) -> tuple[dict[str, AgentSpec], list[GateSpec]]:
    base_yaml = Path(__file__).parent / "agents.yaml"
    manifests = [base_yaml]
    
    if agent_defs_dir:
        extra = Path(agent_defs_dir) / "agents.yaml"
        if extra.is_file():
            manifests.append(extra)
            
    agents_out = {}
    gates_out = []
    
    for path in manifests:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
            
        for action_id, info in data.get("agents", {}).items():
            role = info.get("role", action_id.split(":")[0])
            tools = info.get("tools", ["run_bash", "write_file", "read_file", "str_replace", "list_files"])
            agents_out[action_id] = AgentSpec(
                role=role,
                prompt=info["prompt"],
                task=info["task"],
                tools=tools,
                extra_dir=agent_defs_dir if path != base_yaml else None
            )
            
        for g in data.get("gates", []):
            gates_out.append(GateSpec(
                stage=g["stage"],
                placement=g["placement"],
                generator=g.get("generator"),
                critic=g["critic"],
                reviser=g.get("reviser"),
                verdict_file=g["verdict_file"],
                verdict_key=g["verdict_key"],
                max_iterations=g.get("max_iterations", 1),
                blocking=g.get("blocking", False)
            ))
            
    return agents_out, gates_out


async def run_agent(ctx: AgentContext, agent_spec: AgentSpec, nudge: str | None = None, **kw) -> AgentResult:
    sys_prompt = prompts.render(agent_spec.prompt, extra_dir=agent_spec.extra_dir)
    
    # Safe substitution for task
    task_str = prompts.render_string(
        agent_spec.task,
        spec=ctx.spec.text,
        language=ctx.config.language,
        test_command=ctx.config.resolved_test_command(),
        global_spec=ctx.global_section(),
        **kw
    )
    
    if nudge:
        task_str += f"\n\n{nudge}"
        
    return await ctx.engine.run_agent(
        system_prompt=sys_prompt,
        task=task_str,
        workspace=ctx.workspace.root,
        tools=agent_spec.tools,
        model=ctx.config.model,
        effort=ctx.config.effort
    )

def _truncate(text: str, max_len: int = 1500) -> str:
    if len(text) > max_len:
        return "... [truncated] ...\n" + text[-max_len:]
    return text
