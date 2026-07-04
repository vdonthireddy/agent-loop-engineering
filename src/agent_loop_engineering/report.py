from dataclasses import dataclass, field
from typing import Any

@dataclass(slots=True)
class StageReport:
    name: str
    ok: bool
    detail: str = ""
    files_touched: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RunReport:
    spec_title: str
    engine: str
    model: str
    tests_passed: bool = False
    iterations_used: int = 0
    max_iterations: int = 0
    
    design_approved: bool | None = None
    design_issues: list[dict] = field(default_factory=list)
    design_iterations: int = 0
    
    smoke_passed: bool | None = None
    smoke_iterations: int = 0
    
    conformant: bool | None = None
    conformance_issues: list[dict] = field(default_factory=list)
    conformance_iterations: int = 0
    
    stages: list[StageReport] = field(default_factory=list)
    stopped_after: str | None = None

    @property
    def ok(self) -> bool:
        stages_ok = all(s.ok for s in self.stages)
        if self.stopped_after:
            return stages_ok and self.design_approved is not False and self.smoke_passed is not False and self.conformant is not False
        return (
            stages_ok
            and self.tests_passed
            and self.design_approved is not False
            and self.smoke_passed is not False
            and self.conformant is not False
        )

    @property
    def stopped_at_design_gate(self) -> bool:
        return self.design_approved is False and not self.tests_passed

    def add_stage(self, stage: StageReport):
        self.stages.append(stage)

    def to_markdown(self) -> str:
        lines = []
        overall = "SUCCESS" if self.ok else "INCOMPLETE"
        lines.append(f"# BUILD RESULT: {overall}")
        lines.append("")
        lines.append(f"- **Spec:** {self.spec_title}")
        lines.append(f"- **Engine:** {self.engine}")
        lines.append(f"- **Model:** {self.model}")
        
        if self.design_approved is not None:
            lines.append(f"- **Design Approved:** {_verdict_label(self.design_approved)} ({self.design_iterations} cycles)")
            
        if self.stopped_at_design_gate:
            lines.append("- **Stopped at design gate — no code was generated.**")
        else:
            lines.append(f"- **Tests Passed:** {'yes' if self.tests_passed else 'no'} ({self.iterations_used}/{self.max_iterations} iterations)")
            if self.smoke_passed is not None:
                lines.append(f"- **Smoke Run (app starts):** {'yes' if self.smoke_passed else 'no'} ({self.smoke_iterations} fix cycles)")
            if self.conformant is not None:
                lines.append(f"- **Spec Conformant:** {_verdict_label(self.conformant)} ({self.conformance_iterations} cycles)")
        
        if self.stopped_after:
            lines.append(f"- **STOPPED deliberately after stage:** {self.stopped_after}")
            
        lines.append("")
        lines.append("## Stages")
        for st in self.stages:
            icon = "✅" if st.ok else "❌"
            lines.append(f"### {icon} {st.name}")
            if st.detail:
                lines.append(st.detail)
            if st.files_touched:
                lines.append("**Files touched:** " + ", ".join(st.files_touched))
            lines.append("")
            
        if self.design_issues:
            lines.append("## Remaining Design Issues")
            for issue in self.design_issues:
                lines.append(f"- **{issue.get('severity', 'unknown')}**: {issue.get('requirement', '')} - {issue.get('detail', '')}")
            lines.append("")
            
        if self.conformance_issues:
            lines.append("## Remaining Conformance Issues")
            for issue in self.conformance_issues:
                lines.append(f"- **{issue.get('severity', 'unknown')}**: {issue.get('requirement', '')} - {issue.get('detail', '')}")
            lines.append("")

        return "\n".join(lines)


def _verdict_label(value: bool | None) -> str:
    if value is None:
        return "skipped"
    return "yes" if value else "no"
