import os
import tomllib
from dataclasses import dataclass
from typing import Any


DEFAULT_MODEL = "claude-opus-4-8"
DEFAULT_EFFORT = "xhigh"
DEFAULT_ENGINE = "claude_api"
DEFAULT_MAX_ITERATIONS = 6
DEFAULT_MAX_CONFORMANCE_ITERATIONS = 2
DEFAULT_MAX_DESIGN_ITERATIONS = 3
DEFAULT_MAX_SMOKE_ITERATIONS = 2
DEFAULT_MAX_TEST_REVIEW_ITERATIONS = 2
DEFAULT_LANGUAGE = "python"
_CONFIG_FILENAME = ".agentloop.toml"

_DEFAULT_TEST_COMMANDS = {
    "python": "python -m pytest -q",
    "node": "npm test",
    "javascript": "npm test",
    "typescript": "npm test",
    "go": "go test ./...",
    "rust": "cargo test",
}


@dataclass(slots=True)
class AppConfig:
    engine: str = DEFAULT_ENGINE
    model: str = DEFAULT_MODEL
    effort: str = DEFAULT_EFFORT
    max_iterations: int = DEFAULT_MAX_ITERATIONS
    language: str = DEFAULT_LANGUAGE
    test_command: str | None = None
    design_review: bool = True
    max_design_iterations: int = DEFAULT_MAX_DESIGN_ITERATIONS
    smoke_run: bool = True
    max_smoke_iterations: int = DEFAULT_MAX_SMOKE_ITERATIONS
    test_review: bool = True
    max_test_review_iterations: int = DEFAULT_MAX_TEST_REVIEW_ITERATIONS
    conformance: bool = True
    max_conformance_iterations: int = DEFAULT_MAX_CONFORMANCE_ITERATIONS
    strict_gate: bool = False
    stop_after: str | None = None
    agent_defs_dir: str | None = None
    verbose: bool = False
    run_log: bool = True
    max_retries: int = 2
    request_timeout: float = 120.0
    max_turns: int = 60
    base_url: str = "localhost:11434/v1"
    dry_run: bool = False
    roles: dict[str, dict[str, str]] = __import__('dataclasses').field(default_factory=dict)

    def role_engine_model_effort(self, role: str) -> tuple[str, str, str]:
        role_conf = self.roles.get(role, {})
        eng = role_conf.get("engine", self.engine)
        mod = role_conf.get("model", self.model)
        eff = role_conf.get("effort", self.effort)
        return eng, mod, eff

    def resolved_test_command(self) -> str:
        if self.test_command:
            return self.test_command
        return _DEFAULT_TEST_COMMANDS.get(self.language.lower(), "pytest -q")

    @classmethod
    def resolve(
        cls,
        *,
        overrides: dict[str, Any] | None = None,
        config_dir: str | None = None,
        env: dict[str, str] | None = None,
        project: str | None = None
    ) -> "AppConfig":
        if env is None:
            env = dict(os.environ)
        
        merged = {}
        
        # 1. Env vars
        merged.update(_from_env(env))
        
        # 2. Config file
        file_conf, engine_profiles, project_profiles, stages, roles_conf = _from_file(config_dir)
        merged.update(file_conf)
        
        # Project profile
        if project and project in project_profiles:
            merged.update(project_profiles[project])
            
        # Determine engine to apply engine profile
        tmp_engine = merged.get("engine", DEFAULT_ENGINE)
        if overrides and overrides.get("engine") is not None:
            tmp_engine = overrides["engine"]
            
        if tmp_engine in engine_profiles:
            merged.update(engine_profiles[tmp_engine])

        # 3. CLI Overrides
        if overrides:
            for k, v in overrides.items():
                if v is not None:
                    merged.update({k: v})

        # Keep only valid fields
        valid_keys = {f for f in cls.__annotations__.keys()}
        final_dict = {k: v for k, v in merged.items() if k in valid_keys}
        final_dict["roles"] = roles_conf
        return cls(**final_dict)


def _from_env(env: dict[str, str]) -> dict[str, Any]:
    res = {}
    mapping = {
        "AGENTLOOP_ENGINE": "engine",
        "AGENTLOOP_MODEL": "model",
        "AGENTLOOP_EFFORT": "effort",
        "AGENTLOOP_LANGUAGE": "language",
        "AGENTLOOP_TEST_COMMAND": "test_command",
    }
    for env_key, field in mapping.items():
        if env_key in env:
            res[field] = env[env_key]

    int_mapping = {
        "AGENTLOOP_MAX_ITERATIONS": "max_iterations",
        "AGENTLOOP_MAX_CONFORMANCE_ITERATIONS": "max_conformance_iterations",
        "AGENTLOOP_MAX_DESIGN_ITERATIONS": "max_design_iterations",
        "AGENTLOOP_MAX_SMOKE_ITERATIONS": "max_smoke_iterations",
    }
    for env_key, field in int_mapping.items():
        if env_key in env:
            try:
                res[field] = int(env[env_key])
            except ValueError:
                pass

    bool_mapping = {
        "AGENTLOOP_CONFORMANCE": "conformance",
        "AGENTLOOP_VERBOSE": "verbose",
        "AGENTLOOP_DESIGN_REVIEW": "design_review",
        "AGENTLOOP_SMOKE_RUN": "smoke_run",
    }
    for env_key, field in bool_mapping.items():
        if env_key in env:
            res[field] = env[env_key].lower() not in {"0", "false", "no"}

    return res


def _from_file(config_dir: str | None) -> tuple[dict, dict, dict, dict, dict]:
    d = config_dir or "."
    path = os.path.join(d, _CONFIG_FILENAME)
    if not os.path.exists(path):
        return {}, {}, {}, {}, {}

    with open(path, "rb") as f:
        try:
            data = tomllib.load(f)
        except Exception:
            return {}, {}, {}, {}, {}

    base = data.get("agentloop", data)
    
    # Exclude nested tables from base
    base_dict = {k: v for k, v in base.items() if not isinstance(v, dict)}
    
    engine_profiles = base.get("engines", {})
    project_profiles = base.get("projects", {})
    stages = base.get("stages", {})
    roles_conf = base.get("roles", {})

    return base_dict, engine_profiles, project_profiles, stages, roles_conf
