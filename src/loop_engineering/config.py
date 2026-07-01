"""Configuration — environment-driven settings for the loop engineering demo."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings:
    """All tunables, driven by env vars with sensible defaults."""

    def __init__(self) -> None:
        # ── Ollama ──────────────────────────────────────────────
        self.ollama_url: str = os.getenv(
            "LOOP_ENG_OLLAMA_URL", "http://localhost:11434"
        )
        self.model: str = os.getenv("LOOP_ENG_MODEL", "qwen2.5-coder:0.5b")

        # ── Workspace (where the agent writes generated code) ──
        default_workspace = PROJECT_ROOT / "workspace"
        env_ws = os.getenv("LOOP_ENG_WORKSPACE")
        self.workspace: Path = Path(env_ws) if env_ws else default_workspace

        # ── Spec file ──────────────────────────────────────────
        default_spec = PROJECT_ROOT / "spec.md"
        env_spec = os.getenv("LOOP_ENG_SPEC")
        self.spec_path: Path = Path(env_spec) if env_spec else default_spec

        # ── Loop limits ────────────────────────────────────────
        self.max_agentic_iterations: int = int(
            os.getenv("LOOP_ENG_MAX_AGENTIC_ITER", "5")
        )
        self.max_developer_rounds: int = int(
            os.getenv("LOOP_ENG_MAX_DEV_ROUNDS", "10")
        )
        self.max_external_rounds: int = int(
            os.getenv("LOOP_ENG_MAX_EXT_ROUNDS", "5")
        )

        # ── History file ───────────────────────────────────────
        self.history_path: Path = PROJECT_ROOT / "loop_history.json"


settings = Settings()
