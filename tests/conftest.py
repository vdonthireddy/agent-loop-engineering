import json
import pytest
from pathlib import Path
from typing import Sequence

from agent_loop_engineering.engines.base import AgentResult, Engine
from agent_loop_engineering.engines import registry
from agent_loop_engineering.workspace import Workspace

class FakeEngine:
    name = "fake"
    
    def __init__(self):
        self.design_reject_first = False
        self.design_never_approve = False
        self.smoke_fail = False
        self._design_revised = False
        self._conf_fixed = False
        
    async def run_agent(self, *, system_prompt: str, task: str, workspace: Path,
                        tools: Sequence[str], model: str, effort: str) -> AgentResult:
        ws = Workspace(workspace)
        print(f'PROMPT: {repr(system_prompt)}\nTASK: {repr(task)}\n---')
        files_touched = []
        
        # design critic
        if "Design Critic" in system_prompt:
            approved = True
            issues = []
            
            if self.design_never_approve:
                approved = False
                issues = [{"severity": "high", "detail": "Never approve", "requirement": "all"}]
            elif self.design_reject_first and not self._design_revised:
                approved = False
                issues = [{"severity": "high", "detail": "Needs revision", "requirement": "all"}]
                
            content = json.dumps({"approved": approved, "issues": issues})
            ws.write_file("design_review.json", content)
            files_touched.append("design_review.json")
            return AgentResult(text=content, files_touched=files_touched, tool_calls=[])
            
        # architect revise
        if "Architect" in system_prompt and "Revise" in system_prompt:
            ws.write_file("design.md", "# Revised Design")
            files_touched.append("design.md")
            self._design_revised = True
            return AgentResult(text="Revised design", files_touched=files_touched, tool_calls=[])
            
        # architect (initial)
        if "Architect" in system_prompt and "Read the BRD" in system_prompt:
            ws.write_file("design.md", "# Initial Design")
            files_touched.append("design.md")
            return AgentResult(text="Initial design", files_touched=files_touched, tool_calls=[])
            
        # coder-fix
        if "Coder" in system_prompt and "tests failed" in system_prompt:
            ws.write_file("app.py", "VALUE = 2\n")
            files_touched.append("app.py")
            return AgentResult(text="Fixed source", files_touched=files_touched, tool_calls=[])
            
        # coder (initial)
        if "Coder" in system_prompt and "Implement the approved design" in system_prompt:
            # write wrong value initially
            ws.write_file("app.py", "VALUE = 111\n# Different length to invalidate pyc cache\n")
            files_touched.append("app.py")
            return AgentResult(text="Wrote source", files_touched=files_touched, tool_calls=[])
            
        # smoke
        if "Smoke Tester" in system_prompt:
            exit_code = "1" if self.smoke_fail else "0"
            content = f"#!/bin/bash\nexit {exit_code}\n"
            ws.write_file("smoke_check.sh", content)
            files_touched.append("smoke_check.sh")
            return AgentResult(text="Wrote smoke script", files_touched=files_touched, tool_calls=[])
            
        # tester
        if "Tester" in system_prompt and "Smoke" not in system_prompt:
            content = "import app\nassert app.VALUE == 2\n"
            ws.write_file("check.py", content)
            files_touched.append("check.py")
            return AgentResult(text="Wrote tests", files_touched=files_touched, tool_calls=[])
            
        # deployer
        if "Deployer" in system_prompt:
            ws.write_file("deploy.sh", "#!/bin/bash\necho deploy")
            files_touched.append("deploy.sh")
            return AgentResult(text="Wrote deploy", files_touched=files_touched, tool_calls=[])
            
        # conformance reviewer
        if "Conformance Reviewer" in system_prompt:
            if not self._conf_fixed:
                content = json.dumps({
                    "conformant": False,
                    "issues": [{"severity": "high", "detail": "Missing feature", "requirement": "all"}]
                })
            else:
                content = json.dumps({"conformant": True, "issues": []})
                
            ws.write_file("conformance.json", content)
            files_touched.append("conformance.json")
            return AgentResult(text=content, files_touched=files_touched, tool_calls=[])
            
        # conformance fixer
        if "Fixer" in system_prompt:
            ws.write_file("app.py", "VALUE = 2\n# Added missing feature\n")
            files_touched.append("app.py")
            self._conf_fixed = True
            return AgentResult(text="Fixed conformance", files_touched=files_touched, tool_calls=[])
            
        return AgentResult(text="unknown role", files_touched=[], tool_calls=[])

@pytest.fixture
def fake_engine_registered():
    engine = FakeEngine()
    registry.register("fake", lambda: engine)
    yield engine
