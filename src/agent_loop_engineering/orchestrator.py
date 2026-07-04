import datetime
import json
import re
import copy
import dataclasses
from typing import Callable
from pathlib import Path

from .agents import AgentContext, AgentSpec, load_registry, run_agent, GateSpec
from .config import AppConfig
from .engines.registry import get_engine
from . import prompts
from .prompts import VERDICT_JSON_NUDGE, SMOKE_WRITE_NUDGE
from .report import RunReport, StageReport
from .spec import SpecDocument
from .workspace import Workspace


_STAGE_NAMES = ["design", "code", "test", "smoke", "deploy", "conformance"]

def _parse_verdict(raw: str, key: str) -> dict | None:
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if len(lines) >= 2:
            raw = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
            raw = raw.strip()

    def try_parse(s: str):
        try:
            val = json.loads(s)
            if isinstance(val, dict) and key in val:
                if not isinstance(val.get("issues"), list):
                    val["issues"] = []
                return val
        except json.JSONDecodeError:
            pass
        return None

    res = try_parse(raw)
    if res is not None:
        return res

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        return try_parse(raw[start:end+1])
        
    return None

def _issue_key(issue: dict) -> str:
    detail = issue.get("detail") or issue.get("description") or str(issue)
    return f"{issue.get('severity', '')}:{detail}"

def _remember_issues(seen: list[dict], current: list[dict]):
    keys = {_issue_key(i) for i in seen}
    for issue in current:
        if _issue_key(issue) not in keys:
            seen.append(issue)
            keys.add(_issue_key(issue))

def _blocking_issues(verdict: dict) -> list[dict]:
    if not verdict or "issues" not in verdict:
        return []
    return [i for i in verdict["issues"] if str(i.get("severity", "")).lower() in ("high", "medium")]

def _has_blocking(verdict: dict) -> bool:
    return len(_blocking_issues(verdict)) > 0

def _has_source(ws: Workspace) -> bool:
    for f in ws.list_files():
        if f not in ("design.md", "report.md", "design_review.json", "design_review.history.jsonl"):
            return True
    return False

def _has_deploy_artifact(ws: Workspace) -> bool:
    for f in ws.list_files():
        fl = f.lower()
        if "dockerfile" in fl or "deploy.sh" in fl or "deploy.md" in fl or "docker-compose.yml" in fl:
            return True
    return False

def _noop(stage: str, message: str) -> None:
    pass

class Orchestrator:
    def __init__(self, config: AppConfig, *, progress: Callable[[str, str], None] | None = None, run_log: str | None = None):
        self.config = config
        self._progress_cb = progress or _noop
        self.run_log = run_log
        self.agents, self.gates = load_registry(config.agent_defs_dir)
        self._engine_cache = {}

    def _get_engine(self, name: str):
        if name not in self._engine_cache:
            self._engine_cache[name] = get_engine(name)
        return self._engine_cache[name]

    def _agent_ctx(self, base_ctx: AgentContext, role: str) -> AgentContext:
        eng, mod, eff = self.config.role_engine_model_effort(role)
        engine = self._get_engine(eng)
        new_config = dataclasses.replace(base_ctx.config, engine=eng, model=mod, effort=eff)
        return dataclasses.replace(base_ctx, engine=engine, config=new_config)

    async def _run(self, base_ctx: AgentContext, action: str, **kw):
        agent_spec = self.agents.get(action)
        if not agent_spec:
            return None
        ctx = self._agent_ctx(base_ctx, agent_spec.role)
        res = await run_agent(ctx, agent_spec, **kw)
        return res

    def _emit(self, text: str):
        if not self.run_log:
            return
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(self.run_log, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {text}\n")
        except Exception:
            pass

    def progress(self, stage: str, message: str):
        self._progress_cb(stage, message)
        self._emit(f"[{stage}] {message}")

    def _log(self, ws: Workspace, text: str):
        self._emit(text)
        if self.config.verbose:
            try:
                ws.append_file("build.log", text + "\n")
            except Exception:
                pass

    def _log_agent(self, ws: Workspace, stage: str, result):
        if not result:
            return
        self._emit(f"Agent finished: {stage} (stop reason: {result.stop_reason})")
        if self.config.verbose:
            lines = [f"\n--- STAGE: {stage} ---"]
            for tc in result.tool_calls:
                status = "[ok]" if tc.ok else "[ERR]"
                lines.append(f"{status} {tc.name}: {tc.summary}")
            lines.append("--- Agent Output ---")
            lines.append(result.text.strip())
            lines.append("--------------------\n")
            try:
                ws.append_file("build.log", "\n".join(lines) + "\n")
            except Exception:
                pass

    def _emit_result(self, report: RunReport):
        status = "SUCCESS" if report.ok else "INCOMPLETE"
        self._emit(f"BUILD RESULT: {status} | design_approved={report.design_approved} tests_passed={report.tests_passed} smoke_passed={report.smoke_passed} conformant={report.conformant}")

    async def build(self, spec: SpecDocument, workspace: Workspace) -> RunReport:
        report = RunReport(
            spec_title=spec.title,
            engine=self.config.engine,
            model=self.config.model,
            max_iterations=self.config.max_iterations,
        )
        engine = self._get_engine(self.config.engine)
        self.base_ctx = AgentContext(engine=engine, config=self.config, workspace=workspace, spec=spec)
        
        if self.config.verbose:
            workspace.write_file("build.log", "=== BUILD LOG ===\n")

        for name in _STAGE_NAMES:
            if await self._run_gates(f"pre_{name}", self.base_ctx, report):
                return self._finalize(report, workspace)

            method = getattr(self, f"_stage_{name}", None)
            if method:
                halt = await method(self.base_ctx, report)
                if halt:
                    return self._finalize(report, workspace)

            if self._stop_after(name, report):
                return self._finalize(report, workspace)

            if await self._run_gates(f"post_{name}", self.base_ctx, report):
                return self._finalize(report, workspace)

        return self._finalize(report, workspace)

    def _stop_after(self, stage: str, report: RunReport) -> bool:
        if self.config.stop_after == stage:
            report.stopped_after = stage
            self.progress(stage, f"Stopping after {stage}...")
            return True
        return False

    def _finalize(self, report: RunReport, workspace: Workspace) -> RunReport:
        workspace.write_file("report.md", report.to_markdown())
        self._emit_result(report)
        return report

    async def _run_gates(self, placement: str, ctx: AgentContext, report: RunReport) -> bool:
        for gate in self.gates:
            if gate.stage in ("design", "conformance"):
                continue  # These are built-in stages, not declarative gates
            if gate.placement == placement:
                halt = await self._critique_gate(gate, ctx, report)
                if halt and gate.blocking:
                    report.stopped_after = f"{gate.stage} ({placement} gate blocked)"
                    return True
                if self._stop_after(gate.stage, report):
                    return True
        return False

    async def _critique_gate(self, gate: GateSpec, ctx: AgentContext, report: RunReport) -> bool:
        if gate.generator:
            res = await self._run(ctx, gate.generator)
            self._log_agent(ctx.workspace, f"{gate.stage}: generator", res)

        iterations = 0
        while iterations < gate.max_iterations:
            iterations += 1
            
            async def review_fn(nudge=None):
                res_review = await self._run(ctx, gate.critic, nudge=nudge)
                self._log_agent(ctx.workspace, f"{gate.stage}: critic ({iterations})", res_review)
                return res_review

            verdict, res_review = await self._reviewed_verdict(
                ctx, review_fn, gate.verdict_file, gate.verdict_key, stage=gate.stage, label=f"cycle {iterations}"
            )

            if verdict is None:
                if self.config.strict_gate:
                    report.add_stage(StageReport(name=gate.stage, ok=False, detail="No parseable verdict"))
                    return True # halt
                else:
                    self.progress(gate.stage, "WARNING: Unparseable verdict, failing open.")
                    report.add_stage(StageReport(name=gate.stage, ok=True, detail="Unparseable verdict, skipped"))
                    return False

            approved = verdict.get(gate.verdict_key, False)
            issues = _blocking_issues(verdict)

            if approved or not issues or not gate.reviser:
                report.add_stage(StageReport(name=gate.stage, ok=approved, detail=f"Issues: {len(issues)}"))
                return not approved

            issues_str = json.dumps(issues, indent=2)
            res_fix = await self._run(ctx, gate.reviser, issues=issues_str)
            self._log_agent(ctx.workspace, f"{gate.stage}: reviser ({iterations})", res_fix)

        report.add_stage(StageReport(name=gate.stage, ok=False, detail="Max iterations reached without approval"))
        return True # halt

    async def _stage_design(self, ctx: AgentContext, report: RunReport) -> bool:
        if not self.config.design_review:
            res = await self._run(ctx, "architect")
            self._log_agent(ctx.workspace, "architect.design", res)
            report.add_stage(StageReport(name="design", ok=True, files_touched=res.files_touched if res else []))
            return False
            
        self.progress("design", "Generating technical design...")
        return await self._design_loop(ctx, report)

    async def _stage_code(self, ctx: AgentContext, report: RunReport) -> bool:
        self.progress("code", "Starting coding...")
        res_coder = await self._run(ctx, "coder")
        self._log_agent(ctx.workspace, "coder", res_coder)
        report.add_stage(StageReport(name="code", ok=True, files_touched=res_coder.files_touched if res_coder else []))
        return False

    async def _stage_test(self, ctx: AgentContext, report: RunReport) -> bool:
        self.progress("test", "Testing...")
        await self._test_loop(ctx, report)
        
        if self.config.test_review and report.tests_passed and self.agents.get("test_critic"):
            self.progress("test", "Test review loop...")
            await self._test_review_loop(ctx, report)
        return False

    async def _stage_smoke(self, ctx: AgentContext, report: RunReport) -> bool:
        if self.config.smoke_run:
            self.progress("smoke", "Starting smoke check...")
            await self._smoke_loop(ctx, report)
        return False

    async def _stage_deploy(self, ctx: AgentContext, report: RunReport) -> bool:
        self.progress("deploy", "Writing deployment artifacts...")
        res = await self._run(ctx, "deployer")
        self._log_agent(ctx.workspace, "deploy", res)
        report.add_stage(StageReport(name="deploy", ok=True, files_touched=res.files_touched if res else []))
        return False

    async def _stage_conformance(self, ctx: AgentContext, report: RunReport) -> bool:
        if self.config.conformance:
            self.progress("conformance", "Starting conformance review...")
            await self._conformance_loop(ctx, report)
        return False

    async def _design_loop(self, ctx: AgentContext, report: RunReport) -> bool:
        res = await self._run(ctx, "architect")
        self._log_agent(ctx.workspace, "architect.design", res)

        if not self.agents.get("design_critic"):
            report.design_approved = True
            report.add_stage(StageReport(name="design", ok=True))
            return False

        iterations = 0
        seen = []
        verdict = None
        
        while iterations < self.config.max_design_iterations:
            iterations += 1
            
            async def review_fn(nudge=None):
                res_review = await self._run(ctx, "design_critic", nudge=nudge)
                self._log_agent(ctx.workspace, f"critic.review ({iterations})", res_review)
                return res_review

            verdict, _ = await self._reviewed_verdict(
                ctx, review_fn, "design_review.json", "approved", stage="design", label=f"cycle {iterations}"
            )
            
            if verdict is None:
                if self.config.strict_gate:
                    report.design_approved = False
                    report.add_stage(StageReport(name="design", ok=False, detail="No parseable verdict"))
                    return True # halt
                else:
                    self.progress("design", "WARNING: Unparseable verdict, failing open.")
                    report.add_stage(StageReport(name="design", ok=ctx.workspace.exists("design.md"), detail="Unparseable verdict, skipped"))
                    return False # don't halt

            approved = verdict.get("approved", False)
            issues = _blocking_issues(verdict)
            self._record_design_verdict(ctx.workspace, iterations, verdict)
            
            report.design_approved = approved
            report.design_issues = issues
            report.design_iterations = iterations

            if approved or not issues or not self.agents.get("architect:revise"):
                break
                
            _remember_issues(seen, issues)
            hist_str = json.dumps(seen, indent=2)
            issues_str = json.dumps(issues, indent=2)
            
            res_fix = await self._run(ctx, "architect:revise", issues=issues_str, history=hist_str)
            self._log_agent(ctx.workspace, f"architect.revise ({iterations})", res_fix)

        report.add_stage(StageReport(name="design", ok=report.design_approved or False, detail=f"Cycles: {iterations}"))
        return not report.design_approved

    def _record_design_verdict(self, ws: Workspace, cycle: int, verdict: dict):
        try:
            entry = {"cycle": cycle, "approved": verdict.get("approved", False), "issues": verdict.get("issues", [])}
            ws.append_file("design_review.history.jsonl", json.dumps(entry) + "\n")
        except Exception:
            pass

    async def _test_loop(self, ctx: AgentContext, report: RunReport):
        res_test = await self._run(ctx, "tester")
        self._log_agent(ctx.workspace, "tester", res_test)

        test_cmd = ctx.config.resolved_test_command()
        iterations = 0
        run_ok = False
        cmd_res = None
        
        while iterations < self.config.max_iterations:
            iterations += 1
            cmd_res = ctx.workspace.run_command(test_cmd)
            run_ok = cmd_res.ok
            
            if run_ok or iterations >= self.config.max_iterations or not self.agents.get("coder:fix"):
                break
                
            out_trunc = cmd_res.combined_output[-4000:] if len(cmd_res.combined_output) > 4000 else cmd_res.combined_output
            res_fix = await self._run(ctx, "coder:fix", test_output=out_trunc)
            self._log_agent(ctx.workspace, f"coder_fix ({iterations})", res_fix)

        report.tests_passed = run_ok
        report.iterations_used = iterations
        
        if cmd_res:
            report.add_stage(StageReport(
                name="tester",
                ok=run_ok,
                detail=f"Exit {cmd_res.exit_code}. Output:\n{cmd_res.combined_output[-1500:]}"
            ))
        else:
            report.add_stage(StageReport(name="tester", ok=False, detail="Tests did not run."))

    async def _test_review_loop(self, ctx: AgentContext, report: RunReport):
        iterations = 0
        test_cmd = ctx.config.resolved_test_command()
        seen = []
        
        while iterations < self.config.max_test_review_iterations:
            iterations += 1
            
            async def review_fn(nudge=None):
                res_review = await self._run(ctx, "test_critic", nudge=nudge)
                self._log_agent(ctx.workspace, f"test_critic ({iterations})", res_review)
                return res_review

            verdict, res_review = await self._reviewed_verdict(
                ctx, review_fn, "test_review.json", "adequate", stage="test_review", label=f"cycle {iterations}"
            )
            
            if verdict is None:
                break

            adequate = verdict.get("adequate", False)
            issues = _blocking_issues(verdict)
            _remember_issues(seen, issues)
            
            if adequate or not issues or not self.agents.get("tester:revise"):
                break
                
            issues_str = json.dumps(issues, indent=2)
            hist_str = json.dumps(seen, indent=2)
            res_fix = await self._run(ctx, "tester:revise", issues=issues_str, history=hist_str)
            self._log_agent(ctx.workspace, f"tester:revise ({iterations})", res_fix)
            
            cmd_res = ctx.workspace.run_command(test_cmd)
            if not cmd_res.ok:
                out_trunc = cmd_res.combined_output[-4000:] if len(cmd_res.combined_output) > 4000 else cmd_res.combined_output
                await self._run(ctx, "coder:fix", test_output=out_trunc)

    async def _smoke_loop(self, ctx: AgentContext, report: RunReport):
        if not self.agents.get("smoke"):
            return

        iterations = 0
        run_ok = False
        cmd_res = None
        while iterations < self.config.max_smoke_iterations:
            iterations += 1
            
            res_smoke = await self._run(ctx, "smoke")
            self._log_agent(ctx.workspace, f"smoke.write ({iterations})", res_smoke)
            
            if not ctx.workspace.exists("smoke_check.sh"):
                self._recover_smoke_script(ctx.workspace, res_smoke)
                
            if not ctx.workspace.exists("smoke_check.sh"):
                res_retry = await self._run(ctx, "smoke", nudge=prompts.render(SMOKE_WRITE_NUDGE))
                self._log_agent(ctx.workspace, f"smoke.write.retry ({iterations})", res_retry)
                self._recover_smoke_script(ctx.workspace, res_retry)
                
            if not ctx.workspace.exists("smoke_check.sh"):
                self._emit("FAIL: smoke_check.sh missing after retry")
                report.smoke_passed = False
                report.add_stage(StageReport(name="smoke", ok=False, detail="Missing smoke_check.sh"))
                return

            cmd_res = ctx.workspace.run_command("bash smoke_check.sh", timeout=120)
            run_ok = cmd_res.ok
            
            if run_ok or iterations >= self.config.max_smoke_iterations or not self.agents.get("coder:fix"):
                break
                
            out_trunc = "<smoke failed>\n" + (cmd_res.combined_output[-4000:] if len(cmd_res.combined_output) > 4000 else cmd_res.combined_output)
            res_fix = await self._run(ctx, "coder:fix", test_output=out_trunc)
            self._log_agent(ctx.workspace, f"coder_fix from smoke ({iterations})", res_fix)

        report.smoke_passed = run_ok
        report.smoke_iterations = iterations
        if cmd_res:
            report.add_stage(StageReport(
                name="smoke",
                ok=run_ok,
                detail=f"Exit {cmd_res.exit_code}."
            ))
        else:
            report.add_stage(StageReport(name="smoke", ok=False, detail="Smoke script did not run."))

    def _recover_smoke_script(self, ws: Workspace, result) -> None:
        text = result.text or "" if result else ""
        match = re.search(r"```bash\n(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
        script = None
        if match:
            script = match.group(1).strip()
        elif text.strip().startswith("#!"):
            script = text.strip()
            
        if script:
            try:
                ws.write_file("smoke_check.sh", script)
                self._log(ws, "smoke script recovered from agent's message")
            except Exception:
                pass

    async def _conformance_loop(self, ctx: AgentContext, report: RunReport):
        if not self.agents.get("conformance"):
            return

        iterations = 0
        while iterations < self.config.max_conformance_iterations:
            iterations += 1
            
            async def review_fn(nudge=None):
                res_review = await self._run(ctx, "conformance", nudge=nudge)
                self._log_agent(ctx.workspace, f"conformance.review ({iterations})", res_review)
                return res_review

            verdict, res_review = await self._reviewed_verdict(
                ctx, review_fn, "conformance.json", "conformant", stage="conformance", label=f"cycle {iterations}"
            )
            
            if verdict is None:
                if self.config.strict_gate:
                    report.conformant = False
                    report.add_stage(StageReport(name="conformance", ok=False, detail="No parseable verdict"))
                else:
                    self.progress("conformance", "WARNING: Unparseable verdict, failing open.")
                    report.add_stage(StageReport(name="conformance", ok=True, detail="Unparseable verdict, skipping review"))
                return

            conformant = verdict.get("conformant", False)
            issues = _blocking_issues(verdict)
            
            report.conformant = conformant
            report.conformance_issues = issues
            report.conformance_iterations = iterations

            if conformant or not issues or not self.agents.get("conformance:fix"):
                break
                
            issues_str = json.dumps(issues, indent=2)
            res_fix = await self._run(ctx, "conformance:fix", issues=issues_str)
            self._log_agent(ctx.workspace, f"conformance.fix ({iterations})", res_fix)
            
            # Re-run tests to catch regressions
            test_cmd = ctx.config.resolved_test_command()
            cmd_res = ctx.workspace.run_command(test_cmd)
            report.tests_passed = cmd_res.ok

        report.add_stage(StageReport(
            name="conformance",
            ok=report.conformant or False,
            detail=f"Issues: {len(report.conformance_issues)}"
        ))

    async def _reviewed_verdict(self, ctx: AgentContext, review_fn: Callable, filename: str, key: str, *, stage: str, label: str):
        res = await review_fn()
        verdict = self._verdict_from(ctx.workspace, res, filename, key, stage)
        if verdict is not None:
            return verdict, res
            
        self._emit(f"Unparseable verdict in {stage}, retrying with JSON nudge...")
        res = await review_fn(nudge=prompts.render(VERDICT_JSON_NUDGE, filename=filename, key=key))
        verdict = self._verdict_from(ctx.workspace, res, filename, key, stage)
        return verdict, res

    def _read_verdict(self, ws: Workspace, filename: str, key: str) -> dict | None:
        try:
            if ws.exists(filename):
                return _parse_verdict(ws.read_file(filename), key)
        except Exception:
            pass
        return None

    def _verdict_from(self, ws: Workspace, result, filename: str, key: str, stage: str) -> dict | None:
        verdict = self._read_verdict(ws, filename, key)
        if verdict is not None:
            return verdict
            
        if result and result.text:
            verdict = _parse_verdict(result.text, key)
            if verdict is not None:
                self._log(ws, f"verdict recovered from the agent's message in {stage}")
                return verdict
        return None
