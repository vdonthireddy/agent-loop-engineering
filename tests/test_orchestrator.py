import pytest
from pathlib import Path

from agent_loop_engineering.config import AppConfig
from agent_loop_engineering.orchestrator import Orchestrator
from agent_loop_engineering.spec import SpecDocument
from agent_loop_engineering.workspace import Workspace

@pytest.fixture
def e2e_config():
    return AppConfig(
        engine="fake",
        model="fake",
        effort="low",
        max_iterations=2,
        language="python",
        test_command="python check.py",
        design_review=False,
        max_design_iterations=3,
        smoke_run=False,
        max_smoke_iterations=2,
        test_review=False,
        max_test_review_iterations=2,
        conformance=True,
        max_conformance_iterations=2,
        strict_gate=False,
        stop_after=None,
        agent_defs_dir=None,
        verbose=True,
        run_log=False,
        max_retries=1,
        request_timeout=30.0,
        max_turns=5,
        base_url="",
        dry_run=False
    )

@pytest.mark.asyncio
async def test_end_to_end_success(fake_engine_registered, tmp_path, e2e_config):
    ws = Workspace(tmp_path)
    spec = SpecDocument.from_text("# Test Spec")
    
    orch = Orchestrator(e2e_config)
    report = await orch.build(spec, ws)
    
    # Check that loop converges: coder (111) -> tester -> fails -> coder-fix -> passes
    assert report.tests_passed is True
    assert report.iterations_used == 2 # 2 passes
    
    # app.py should have VALUE = 2
    assert "VALUE = 2" in ws.read_file("app.py")
    
    # deployer ran
    assert ws.exists("deploy.sh")
    
    # conformance loop reviews -> fixes -> re-reviews
    assert report.conformant is True
    assert report.conformance_iterations == 2 # FakeEngine reviewer writes False first, then True
    
    assert report.ok is True
    
    # verbose writes build.log
    assert ws.exists("build.log")
    log = ws.read_file("build.log")
    assert "STAGE: architect" in log
    assert "STAGE: coder" in log
    assert "STAGE: tester" in log

@pytest.mark.asyncio
async def test_max_iterations_bound(fake_engine_registered, tmp_path, e2e_config):
    ws = Workspace(tmp_path)
    spec = SpecDocument.from_text("# Test Spec")
    
    # command always fails
    e2e_config.test_command = "exit 1"
    
    orch = Orchestrator(e2e_config)
    report = await orch.build(spec, ws)
    
    assert report.tests_passed is False
    assert report.iterations_used == e2e_config.max_iterations
    assert report.ok is False

@pytest.mark.asyncio
async def test_no_conformance(fake_engine_registered, tmp_path, e2e_config):
    ws = Workspace(tmp_path)
    spec = SpecDocument.from_text("# Test Spec")
    
    e2e_config.conformance = False
    orch = Orchestrator(e2e_config)
    report = await orch.build(spec, ws)
    
    assert report.conformant is None
