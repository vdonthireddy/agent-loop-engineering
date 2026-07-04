# Verification Plan

I am conducting a highly detailed cross-reference between my implementation and `low-level-design-and-coding.md`. 

## Discrepancies Found

### 1. `RunReport.ok` and Stage Appending
- **LLD**: `RunReport.ok` is strictly defined as `all(stage.ok) and tests_passed and conformant is not False and design_approved is not False and smoke_passed is not False`. 
- **My Code**: I changed this to ignore `stage.ok` because I was appending failing stages for every intermediate iteration of the test, smoke, and design loops.
- **Fix**: Revert `RunReport.ok` to strictly check `all(stage.ok)`. Update the Orchestrator's loops (`_design_loop`, `_test_loop`, `_smoke_loop`, `_conformance_loop`) to only append **a single StageReport** at the end of the loop, representing the final outcome (as specified in Section 4.1). 

### 2. `_agent_ctx` Config Overrides
- **LLD**: The orchestrator's `_agent_ctx(base_ctx, role)` builds a per-agent `AgentContext` with a `dataclasses.replace` config containing the role's model/effort (Section 4.1: "The orchestrator loads the registry... scope to the action's role (per-agent model via `_agent_ctx`)").
- **My Code**: My `_agent_ctx` is currently a stub that just returns `base_ctx`.
- **Fix**: Implement `config.role_engine_model_effort(role)` in `AppConfig` and use it in `_agent_ctx` to correctly inject role-specific engine/model/effort overrides.

### 3. Missing `tests/` details in `_test_loop`?
- **LLD**: "tester -> write_tests(ctx) -> writes tests/"
- **My Code**: In `_test_loop`, I just run the tester agent. The actual file writing is done by the engine. But I should verify the exact StageReport names.
- **Fix**: Ensure the `tester` StageReport matches the LLD: "append a `tester` stage whose detail includes the final exit code and the last 1500 chars of output".

### 4. `_critique_gate` Return value
- **LLD**: "halt = await _critique_gate(...)". 
- **My Code**: `_critique_gate` returns `True` if exhausted/rejected, and `False` if approved.
- **Fix**: Verify this matches exactly.

I will proceed to fix these strict LLD violations in a moment. Are there any other specific sections you want me to scrutinize before I begin the fixes?
