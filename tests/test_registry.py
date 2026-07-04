import pytest
from agent_loop_engineering.engines import registry

def test_builtin_engines():
    engines = registry.available_engines()
    assert "claude_api" in engines
    assert "agent_sdk" in engines
    assert "local" in engines
    assert "azure" in engines

def test_unknown_engine():
    with pytest.raises(ValueError):
        registry.get_engine("does_not_exist")

def test_fake_engine_selectable(fake_engine_registered):
    engine = registry.get_engine("fake")
    assert engine.name == "fake"
