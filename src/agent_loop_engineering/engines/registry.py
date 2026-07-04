from collections.abc import Callable

from .base import Engine

_FACTORIES: dict[str, Callable[[], Engine]] = {}


def register(name: str, factory: Callable[[], Engine]) -> None:
    _FACTORIES[name] = factory


def available_engines() -> list[str]:
    return sorted(_FACTORIES.keys())


def get_engine(name: str) -> Engine:
    if name not in _FACTORIES:
        avail = ", ".join(available_engines())
        raise ValueError(f"Unknown engine '{name}'. Available: {avail}")
    return _FACTORIES[name]()


def _make_claude_api() -> Engine:
    from .claude_api import ClaudeAPIEngine
    return ClaudeAPIEngine()


def _make_agent_sdk() -> Engine:
    from .agent_sdk import AgentSDKEngine
    return AgentSDKEngine()


def _make_local() -> Engine:
    from .local import LocalEngine
    return LocalEngine()


def _make_azure() -> Engine:
    from .azure_openai import AzureOpenAIEngine
    return AzureOpenAIEngine()


register("claude_api", _make_claude_api)
register("agent_sdk", _make_agent_sdk)
register("local", _make_local)
register("azure", _make_azure)
