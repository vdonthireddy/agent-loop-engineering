import pytest
import os
from pathlib import Path

from agent_loop_engineering.config import AppConfig
from agent_loop_engineering.orchestrator import Orchestrator
from agent_loop_engineering.spec import SpecDocument
from agent_loop_engineering.workspace import Workspace

@pytest.fixture
def base_config():
    return AppConfig(
        engine="fake",
        model="fake",
        effort="low",
        max_iterations=2,
        language="python",
        test_command="true",
        design_review=True,
        max_design_iterations=3,
        smoke_run=False,
        max_smoke_iterations=2,
        conformance=False,
        max_conformance_iterations=2,
        strict_gate=False,
        stop_after=None,
        agent_defs_dir=None,
        verbose=False,
        run_log=False,
        max_retries=1,
        request_timeout=30.0,
        max_turns=5,
        base_url="",
        dry_run=False
    )

@pytest.mark.asyncio
async def test_design_reject_once_then_approve(fake_engine_registered, tmp_path, base_config):
    fake_engine_registered.design_reject_first = True
    
    ws = Workspace(tmp_path)
    spec = SpecDocument.from_text("# Test Spec\nDo something.")
    
    base_config.stop_after = "code" # Only run up to code
    orch = Orchestrator(base_config)
    report = await orch.build(spec, ws)
    
    assert report.design_iterations == 2
    assert report.design_approved is True
    assert ws.exists("app.py") # coding proceeded
    assert report.stopped_at_design_gate is False

@pytest.mark.asyncio
async def test_design_hard_gate(fake_engine_registered, tmp_path, base_config):
    fake_engine_registered.design_never_approve = True
    
    ws = Workspace(tmp_path)
    spec = SpecDocument.from_text("# Test Spec\nDo something.")
    
    base_config.strict_gate = True
    orch = Orchestrator(base_config)
    report = await orch.build(spec, ws)
    
    assert report.design_approved is False
    assert not ws.exists("app.py") # coder never ran
    assert report.ok is False
    assert report.stopped_at_design_gate is True
    
    report_md = ws.read_file("report.md")
    assert "stopped at design gate" in report_md.lower() or "stopped after design" in report_md.lower()

@pytest.mark.asyncio
async def test_design_approve_first_time(fake_engine_registered, tmp_path, base_config):
    ws = Workspace(tmp_path)
    spec = SpecDocument.from_text("# Test Spec\nDo something.")
    
    base_config.stop_after = "code"
    orch = Orchestrator(base_config)
    report = await orch.build(spec, ws)
    
    assert report.design_iterations == 1
    assert report.design_approved is True
    assert ws.exists("app.py")

@pytest.mark.asyncio
async def test_no_design_review(fake_engine_registered, tmp_path, base_config):
    ws = Workspace(tmp_path)
    spec = SpecDocument.from_text("# Test Spec\nDo something.")
    
    base_config.design_review = False
    base_config.stop_after = "code"
    orch = Orchestrator(base_config)
    report = await orch.build(spec, ws)
    
    assert report.design_approved is None
    assert ws.exists("app.py")
    assert ws.exists("design.md") # architect still produces design.md
