import os
from agent_loop_engineering.config import AppConfig

def test_config_defaults():
    config = AppConfig.resolve()
    assert config.engine == "claude_api"
    assert config.model == "claude-opus-4-8"
    assert config.effort == "xhigh"
    assert config.max_iterations == 6
    assert config.language == "python"

def test_config_precedence(tmp_path):
    # env > file > default
    # flag > env
    
    # 1. file
    toml_path = tmp_path / ".agentloop.toml"
    toml_path.write_text("""
[agentloop]
model = "from-file"
effort = "high"
""")
    
    # 2. env
    env = {
        "AGENTLOOP_MODEL": "from-env",
        "AGENTLOOP_EFFORT": "low"
    }
    
    # 3. flag
    overrides = {
        "model": "from-flag"
    }
    
    config = AppConfig.resolve(overrides=overrides, config_dir=tmp_path, env=env)
    
    # flag wins for model
    assert config.model == "from-flag"
    
    # file wins over env for effort (LLD says: file beats env)
    # Let's check config precedence: CLI flags > .agentloop.toml > env vars > defaults
    assert config.effort == "high"

def test_config_language_test_command_inference():
    config = AppConfig.resolve(overrides={"language": "python"})
    assert "pytest" in config.resolved_test_command()
    
    config = AppConfig.resolve(overrides={"language": "node"})
    assert "npm test" in config.resolved_test_command()
    
    config = AppConfig.resolve(overrides={"language": "go"})
    assert "go test" in config.resolved_test_command()
