# agent-loop-engineering — Low-Level Design & Coding Guide

A file-by-file, function-by-function reference for the `agent-loop-engineering`
framework and its `agentloop` CLI. It is written for an engineer who will
maintain or extend the codebase: every source file is documented with its
responsibility, key classes/functions and their signatures, notable control
flow, and how it connects to the rest of the system.

> Scope note: this document covers the framework in `src/agent_loop_engineering/`,
> its tests in `tests/`, packaging/config, and the `specs/` inputs. Generated
> build outputs (under `workspace/`) are deliberately not documented here.

---

## Table of contents

1. [Overview](#1-overview)
2. [High-level architecture](#2-high-level-architecture)
3. [Directory layout](#3-directory-layout)
4. [Module-by-module low-level design](#4-module-by-module-low-level-design)
   - [4.1 Core](#41-core)
   - [4.2 Engine layer](#42-engine-layer)
   - [4.3 Agents](#43-agents)
5. [Key flows / sequences](#5-key-flows--sequences)
6. [Engine layer contract & adapters](#6-engine-layer-contract--adapters)
7. [CLI reference](#7-cli-reference)
8. [Security model](#8-security-model)
9. [Testing](#9-testing)
10. [Extension points](#10-extension-points)

---

## 1. Overview

`agent-loop-engineering` turns a **single Markdown specification (or a
business-level BRD)** into a working software project — a technical design,
source code, an automated test suite, and a deployment artifact — by driving a
pipeline of LLM "agents" through repeated review/fix loops until the design is
approved, the tests pass, and the project conforms to the original spec.

The public entry point is a CLI called `agentloop` (declared in
`pyproject.toml` as `agent_loop_engineering.cli:main`). Given a spec, it runs
**stages** in order — **architect → design critic → coder → tester → test critic
→ smoke → deployer → conformance** — each of which asks an LLM to *act* (write
files, run commands) inside a sandboxed output directory. The first two form a
**design-review gate**: the architect derives a technical design and the critic
reviews it, and **coding does not start until the design is approved** (a hard
gate). After the suite goes green, a **test-review** stage has an independent
critic grade the *tests* against the original spec (guarding against tests that
pass trivially because the same model wrote both the code and the tests). Between
unit tests and deployment, a **smoke** stage actually *starts and exercises the
built app* to catch runtime failures unit tests miss.

### Core design principles

- **Spec/BRD-driven.** The Markdown input is the source of truth. It can be a
  low-level `spec.md` *or* a business-level `brd.md` (goals, actors, user
  stories, NFRs — **no** schema or endpoints). Either way the text is read
  wholesale: the **architect** embeds it to *derive* a technical design, and the
  **conformance reviewer** embeds it to grade the finished project. There is also
  a richer, three-layer *composable* spec format (`layered_spec.py`) that
  deterministically composes into one effective spec before the pipeline runs.

- **Design-first, with a hard gate.** Because a BRD leaves the engineering
  decisions open, an **architect** makes them explicit in `design.md` and a
  **design critic** must approve that design (writing `design_review.json`)
  *before* any code is written. An unapproved design stops the build — no coder,
  tester, or deployer runs. This gate is defeatable with `--no-design-review`
  (the architect still writes `design.md` so the coder has something to build).

- **Pluggable engine seam.** The LLM backend sits behind a one-method `Engine`
  protocol (`engines/base.py`). The orchestrator and agents depend only on that
  protocol, so swapping `--engine claude_api` for `--engine local` (or `azure`,
  or `agent_sdk`) changes nothing above the seam. Four adapters ship.

- **Deterministic control loops with the model behind an interface.** The
  *model* decides what to do (it emits tool calls); the *framework* owns the
  loops and the pass/fail decisions. "Tests pass" is a real subprocess exit
  code, not the model's opinion; "design approved" and "spec-conformant" are
  structured verdicts the orchestrator parses and gates on. This split is the
  project's defining idea.

- **Sandboxed execution.** All file I/O and command execution flow through a
  single `Workspace` object confined to the `--out` directory, with
  path-traversal guards and timed subprocesses. Generated code *is* executed
  (to run its tests), so the sandbox is the security boundary.

---

## 2. High-level architecture

### Division of labor

| Job | Who | Where it runs |
|---|---|---|
| Sequence the build; own the loops; decide the design gate & pass/fail | **Orchestrator** (`orchestrator.py`) | local `agentloop` process |
| Build each stage's system prompt + task (inject the spec/BRD) | **Agent manifest** (`agents.yaml` + `prompts/*.md`, loaded by `agents.py`) | local process |
| Make the actual LLM call and drive the tool-use loop | **Engine adapter** (`engines/*.py`) | local process → HTTP → model |
| Think and emit **tool calls** (write file, run command) | **The model** | Anthropic API / local server / Azure |
| Execute those tool calls (write files, run commands) safely | **Workspace** (`workspace.py`) | local process (real disk / subprocess) |
| Run the tests and judge pass/fail from the exit code | **Orchestrator** → `Workspace.run_command` | local subprocess |
| Parse the design/conformance verdicts and gate on them | **Orchestrator** (`_read_verdict`, `_blocking_issues`) | local process |

The single most important idea: **the model never hands back a blob of code that
we save.** The model *requests actions* via tool calls; the Engine *executes*
them through the Workspace. Files appear in the output directory because the
engine ran the model's `write_file`/editor tool calls, not because we parsed code
out of chat text.

### The pipeline (control + data flow)

```
                         (optional pre-pipeline, no LLM)
 project_dir ─▶ load_project ─▶ compose ─▶ SpecDocument.from_text ─┐
   (stack.yaml + features/*.md + customers/*.yaml)                 │
                                                                   ▼
   spec.md / brd.md ─▶ SpecDocument.load ─────────────▶  Orchestrator.build(spec, workspace)
                                                                   │
   ┌───────────────────────────────────────────────────────────────────────────────────┐
   │ Orchestrator (conductor — owns the loops, never calls the model directly)           │
   │                                                                                     │
   │     ┌──────── DESIGN-REVIEW LOOP (orchestrator-owned) — HARD GATE ─────────────┐    │
   │     │ architect.design()  ─▶ writes design.md                                  │    │
   │     │ critic.review()     ─▶ writes design_review.json                         │    │
   │     │ verdict = _read_verdict(ws,"design_review.json","approved")              │    │
   │     │ while not approved and has high/medium issues and cycles left:           │    │
   │     │     architect.revise(issues)   # model edits design.md via tools         │    │
   │     │     critic.review() ; re-parse verdict                                   │    │
   │     │ return whether coding may proceed                                        │    │
   │     └──────────────────────────────────────────────────────────────────────────┘   │
   │            │                                                                         │
   │   design NOT approved ─▶ write report.md, STOP (no code written)                     │
   │            │ approved (or design_review disabled)                                    │
   │            ▼                                                                         │
   │  coder   ─▶ Agent.run ─▶ Engine.run_agent ─▶ [model emits tool calls] ─▶ Workspace   │
   │     └─ writes source + manifests (builds exactly per the approved design.md)         │
   │  tester  ─▶ write_tests()  ─▶ writes tests/                                          │
   │     ┌─────────────── TEST-FIX LOOP (orchestrator-owned) ──────────────┐             │
   │     │ run = Workspace.run_command(test_cmd)                            │             │
   │     │ while not run.ok and iters < max_iterations:                     │             │
   │     │     coder.fix(run.combined_output)   # CODER edits source via tools│             │
   │     │     run = Workspace.run_command(test_cmd)                        │             │
   │     │ report.tests_passed = run.ok  # exit_code == 0 and not timed_out │             │
   │     └──────────────────────────────────────────────────────────────────┘           │
   │  test_critic ─▶ review() ─▶ test_review.json (tests graded vs ORIGINAL spec)         │
   │     ┌──── TEST-REVIEW LOOP (orchestrator-owned; only if tests green) ────┐           │
   │     │ while not adequate and has high/medium issues and cycles left:      │           │
   │     │     tester.revise(issues, history)  # strengthen/repair the tests   │           │
   │     │     run = Workspace.run_command(test_cmd)  # revised tests must pass │           │
   │     │     if not run.ok: coder.fix(output)  # a new test caught a real bug │           │
   │     │     review() ; re-parse verdict                                     │           │
   │     └──────────────────────────────────────────────────────────────────┘           │
   │  smoke   ─▶ write_check() ─▶ writes smoke_check.sh (gated on config.smoke_run)       │
   │     │ if not written: retry write_check(nudge); still missing ⇒ FAIL (smoke_passed=False)│
   │     ┌─────────────── SMOKE LOOP (orchestrator-owned) ──────────────────┐             │
   │     │ run = Workspace.run_command("bash smoke_check.sh", timeout=120)  │             │
   │     │ while not run.ok and iters < max_smoke_iterations:               │             │
   │     │     coder.fix(smoke_output)   # CODER edits source via tools     │             │
   │     │     run = Workspace.run_command("bash smoke_check.sh", ...)      │             │
   │     │ report.smoke_passed = run.ok                                     │             │
   │     └──────────────────────────────────────────────────────────────────┘           │
   │  deployer ─▶ writes deploy.sh / Dockerfile + DEPLOY.md (+ README when spec asks)     │
   │                                                                                     │
   │     ┌────────── CONFORMANCE LOOP (orchestrator-owned, vs ORIGINAL spec) ──────────┐ │
   │     │ conformance.review()  ─▶ model writes conformance.json                       │ │
   │     │ verdict = _read_verdict(ws,"conformance.json","conformant")                  │ │
   │     │ while not conformant and has high/medium issues and cycles left:             │ │
   │     │     conformance.fix(issues)       # model edits code via tools               │ │
   │     │     Workspace.run_command(tests)  # re-check for regressions                 │ │
   │     │     review() ; re-parse verdict                                              │ │
   │     └───────────────────────────────────────────────────────────────────────────┘ │
   │                                                                                     │
   │  write report.md                                                                    │
   └─────────────────────────────────────────────────────────────────────────────────────┘
```

Who does what, explicitly:

- The **Orchestrator** conducts the sequence and owns all five loops (design,
  test-fix, test-review, smoke, conformance); it runs the tests *and* the smoke check and
  judges pass/fail from the process exit code, and it parses the design and
  conformance verdicts (`_read_verdict`) and decides which issues are blocking
  (`_blocking_issues`). It enforces the **design gate**: an unapproved design
  ends the run before coding.
- **Agents** are thin: each builds a *system prompt* (its persona) and a *task*
  (what to do this turn), then calls `engine.run_agent(...)`.
- The **Engine adapter** makes the LLM call, receives tool calls, and dispatches
  them against the Workspace, looping until the model stops.
- The **model** only *requests* actions; it has no filesystem access.
- The **Workspace** performs the actions — the only component that touches disk
  or spawns processes — always inside the `--out` sandbox.

---

## 3. Directory layout

```
agent-loop-engineering/
├── pyproject.toml                     # packaging; deps; extras; `agentloop` script; pytest config
├── README.md                          # user-facing intro + flags
├── ARCHITECTURE.md                    # who-calls-whom narrative
├── .gitignore                         # ignores .env, .venv, caches, build dirs
├── src/agent_loop_engineering/
│   ├── __init__.py                    # version + re-exports (AppConfig, SpecDocument)
│   ├── cli.py                         # Click CLI: build / build-project / compose; .env loader
│   ├── config.py                      # AppConfig + precedence resolution (flags>toml>env>defaults)
│   ├── spec.py                        # SpecDocument: load/validate spec-or-BRD, title, language hint
│   ├── layered_spec.py                # 3-layer spec load + deterministic compose (no LLM)
│   ├── workspace.py                   # sandboxed file I/O + timed run_command (security boundary)
│   ├── orchestrator.py                # pipeline sequencing; design/test/test-review/smoke/conformance loops; report
│   ├── prompts.py                     # prompt loader: load()/render() (${var} safe-subst)
│   ├── prompts/                       # prompt text, one <name>.md per role (data)
│   ├── agents.yaml                    # agent manifest: action -> role/prompt/task/tools + gates
│   ├── report.py                      # RunReport / StageReport → report.md
│   ├── engines/
│   │   ├── __init__.py                # re-exports Engine, value types, registry helpers
│   │   ├── base.py                    # Engine protocol + AgentResult / CommandResult / ToolCall
│   │   ├── registry.py                # name → engine factory (lazy imports); built-in registration
│   │   ├── _openai_common.py          # shared OpenAI function-calling loop + workspace tools
│   │   ├── claude_api.py              # Anthropic SDK adapter (manual bash + text-editor loop)
│   │   ├── agent_sdk.py               # claude-agent-sdk adapter (SDK owns the loop)
│   │   ├── local.py                   # OpenAI-compatible local server (Ollama/LM Studio/vLLM)
│   │   └── azure_openai.py            # Azure OpenAI (deployment-name-as-model)
│   └── agents.py                      # loads agents.yaml -> AgentSpec/GateSpec registry + run_agent()
├── tests/
│   ├── conftest.py                    # offline FakeEngine + fixture (no network)
│   ├── test_cli_env.py                # .env loader behavior
│   ├── test_config.py                 # config precedence + test-command inference
│   ├── test_design_loop.py            # design gate: approve/reject/hard-gate/disabled
│   ├── test_layered_spec.py           # layered load/compose + error cases
│   ├── test_orchestrator.py           # end-to-end pipeline + loops (via FakeEngine)
│   ├── test_registry.py               # engine registration & lookup
│   ├── test_smoke.py                   # smoke stage: passes/disabled/failure feeds coder & gates ok
│   ├── test_spec.py                   # spec title/language/errors
│   └── test_workspace.py              # sandbox guards + run_command
└── specs/                            # inputs only (config lives in .agentloop.toml)
    ├── _brd-template/
    │   └── brd.md                    # BRD template (business-level, no schema/endpoints)
    ├── global/
    │   └── stack.md                  # mandated tech stack fed to architect + critic
    └── leadgen-brd/
        └── brd.md                    # worked BRD example (B2B lead capture)
```

A **layered** project (for `build-project`) is a directory with `stack.yaml`
(Layer 1) + `features/*.md` (Layer 2) + `customers/*.yaml` (Layer 3); no example
ships — see §5f for how compose works.

---

## 4. Module-by-module low-level design

### 4.1 Core

#### `__init__.py`

Package marker. Sets `__version__ = "0.1.0"` and re-exports the two most-used
public types, `AppConfig` and `SpecDocument`, so callers can do
`from agent_loop_engineering import AppConfig`. `__all__` lists both plus
`__version__`.

---

#### `spec.py` — the build spec (or BRD)

Reads and lightly validates the Markdown input — a low-level `spec.md` or a
business-level `brd.md`, treated identically. The input is free-form Markdown;
only a title and an optional language hint are extracted.

- **`class SpecError(Exception)`** — raised when a spec is missing/empty/unusable.

- **`@dataclass(slots=True) class SpecDocument`**
  - Fields: `path: Path`, `text: str`.
  - `SpecDocument.load(path) -> SpecDocument` (classmethod): reads UTF-8, strips
    it, raises `SpecError` if the file is missing or empty.
  - `SpecDocument.from_text(text, *, title=None) -> SpecDocument` (classmethod):
    wraps an **in-memory** spec string — this is how a composed layered spec
    enters the pipeline. `path` becomes a sentinel (`Path(title or
    "composed-spec")`) used only as a title fallback.
  - `title` (property): first Markdown `# H1` (regex `^#\s+(.+)$`), else the
    filename stem. Composed specs always start with an H1, so their title is the
    stack name.
  - `language_hint() -> str | None`: best-effort regex for a line like
    `Language: python` (case-insensitive, multiline: `^\s*language\s*[:=]\s*
    ([A-Za-z0-9_+#-]+)`), lowercased. Returns `None` if absent, letting the
    caller pick the default.

Connections: `cli.build` uses `language_hint()` to seed the language default;
`ArchitectAgent`/`DesignCriticAgent`/`ConformanceAgent`/`DeployerAgent` embed
`spec.text` (the architect and critic against the BRD/spec, the reviewer against
the original spec).

---

#### `config.py` — run configuration & precedence

Resolves all settings for one build, with a precise precedence order.

Module-level defaults:

| Constant | Value |
|---|---|
| `DEFAULT_MODEL` | `"claude-opus-4-8"` |
| `DEFAULT_EFFORT` | `"xhigh"` |
| `DEFAULT_ENGINE` | `"claude_api"` |
| `DEFAULT_MAX_ITERATIONS` | `6` |
| `DEFAULT_MAX_CONFORMANCE_ITERATIONS` | `2` |
| `DEFAULT_MAX_DESIGN_ITERATIONS` | `3` |
| `DEFAULT_MAX_SMOKE_ITERATIONS` | `2` |
| `DEFAULT_MAX_TEST_REVIEW_ITERATIONS` | `2` |
| `DEFAULT_LANGUAGE` | `"python"` |
| `_CONFIG_FILENAME` | `".agentloop.toml"` |

- **`@dataclass(slots=True) class AppConfig`** — resolved settings:

  | Field | Type | Default | Meaning |
  |---|---|---|---|
  | `engine` | `str` | `claude_api` | Engine adapter name |
  | `model` | `str` | `claude-opus-4-8` | Model id |
  | `effort` | `str` | `xhigh` | `output_config.effort` level |
  | `max_iterations` | `int` | `6` | Max test-fix loop iterations |
  | `language` | `str` | `python` | Target language hint |
  | `test_command` | `str \| None` | `None` | Test runner; inferred if unset |
  | `design_review` | `bool` | `True` | Run the architect design + critic gate before coding |
  | `max_design_iterations` | `int` | `3` | Max design review→revise→re-review cycles |
  | `smoke_run` | `bool` | `True` | Run the smoke stage (start/exercise the built app) after tests |
  | `max_smoke_iterations` | `int` | `2` | Max smoke-run→coder-fix cycles |
  | `test_review` | `bool` | `True` | After tests go green, review them against the spec and strengthen weak/missing tests |
  | `max_test_review_iterations` | `int` | `2` | Max test-review→revise→re-review cycles |
  | `conformance` | `bool` | `True` | Run the conformance stage |
  | `max_conformance_iterations` | `int` | `2` | Max review→fix cycles |
  | `strict_gate` | `bool` | `False` | Treat an unparseable verdict (after retry) as blocking instead of failing open |
  | `stop_after` | `str \| None` | `None` | Run only through this stage then stop: `design`/`code`/`test`/`smoke`/`deploy`/`conformance` |
  | `agent_defs_dir` | `str \| None` | `None` | Project dir (`agents.yaml` + `prompts/`) that adds/overrides agents and declares extra gates |
  | `verbose` | `bool` | `False` | Write `<out>/build.log` transcript |
  | `run_log` | `bool` | `True` | Write a timestamped `<out>/run.log` of every observation |
  | `max_retries` | `int` | `2` | SDK retries per request on transient errors (→ `EngineOptions`) |
  | `request_timeout` | `float` | `120.0` | Per-request LLM timeout, seconds (→ `EngineOptions`) |
  | `max_turns` | `int` | `60` | Tool-use turn cap per agent run (→ `EngineOptions`) |
  | `base_url` | `str` | `localhost:11434/v1` | Local engine server URL (→ `EngineOptions`) |
  | `dry_run` | `bool` | `False` | Resolve config + print plan, no LLM |

  Settings come from **one root `.agentloop.toml`** (cwd), so `specs/` stays
  spec-only. It has a base `[agentloop]` table, **project profiles**
  `[agentloop.projects.<slug>]` (slug = the spec's folder name; per-project
  settings like `test_command`), and **engine profiles**
  `[agentloop.engines.<name>]` (applied only when that engine is resolved — e.g.
  `[agentloop.engines.local]` gives local models a 20-per-stage budget without
  touching azure). `AppConfig.resolve(config_dir=..., project=...)` first picks
  the engine (from CLI > project profile > base > env), then merges, precedence
  (low→high): defaults < env < base < project profile < engine profile < CLI
  flags. `_from_file` returns `(base, engine_profiles, project_profiles, stages)`;
  `config_files_for()` lists the loaded file for the banner.

  **Per-stage / per-agent models:** `[agentloop.stages.<stage>]` →
  `stage_overrides`; `[agentloop.agents.<role>]` → `agent_overrides`.
  `config.role_engine_model_effort(role, azure_deployment=…)` resolves an agent's
  `(engine, model, effort)` with precedence **agents.<role> > stages.<role's
  stage> > base** (`_ROLE_STAGE` maps each role to its stage; an azure override
  without a model uses the deployment name). The orchestrator's
  `_agent_ctx(base_ctx, role)` builds a per-agent `AgentContext` — its own engine
  (cached `_get_engine`) + a `dataclasses.replace` config with the role's model/
  effort, sharing workspace/spec/global_spec/notes — returning the base ctx
  unchanged when nothing overrides it. Each loop resolves a ctx per agent (e.g.
  `_design_loop` builds `arch_ctx` and `crit_ctx` separately), so the architect
  and design critic can run on different models, and the design gate can run on a
  frontier model while coding/testing stay local.

  **Global spec:** `orchestrator.load_global_spec(config.global_spec_dir)` reads
  every `*.md` in `specs/global/` (default) and stores it on
  `AgentContext.global_spec`. `AgentContext.global_section()` formats it as a task
  section that the **architect** (design + revise) and **design critic** append
  to their prompts — mandated tech stack + cross-cutting constraints applied to
  every build, on top of the per-project BRD. The
  resilience/tuning knobs are bundled into an `EngineOptions` dataclass
  (`engines/base.py`) that `Orchestrator.build` passes to `get_engine(name,
  options)`; each adapter applies `max_retries`/`request_timeout` to its SDK
  client and `max_turns` to its tool loop.

  - `AppConfig.resolve(*, overrides=None, config_dir=None, env=None) -> AppConfig`
    (classmethod): builds config by applying, in order (later wins):
    1. env vars (`_from_env`),
    2. config file (`_from_file`),
    3. explicit `overrides` (CLI flags) — but **`None` values are dropped** so an
       unset flag never overrides a lower source.
    Finally it keeps only keys matching dataclass field names and constructs the
    instance. `env` defaults to a copy of `os.environ`; injectable for tests.
  - `resolved_test_command() -> str`: returns `test_command` if set, else looks
    up `_DEFAULT_TEST_COMMANDS` by language, falling back to `"pytest -q"`.

- **`_DEFAULT_TEST_COMMANDS`** maps language → command: `python` →
  `python -m pytest -q`, `node`/`javascript`/`typescript` → `npm test`, `go` →
  `go test ./...`, `rust` → `cargo test`.

- **`_from_env(env) -> dict`**: maps `AGENTLOOP_ENGINE/MODEL/EFFORT/LANGUAGE/
  TEST_COMMAND` to fields; parses `AGENTLOOP_MAX_ITERATIONS`,
  `AGENTLOOP_MAX_CONFORMANCE_ITERATIONS`, `AGENTLOOP_MAX_DESIGN_ITERATIONS`, and
  `AGENTLOOP_MAX_SMOKE_ITERATIONS` as ints (ignoring parse errors); reads
  `AGENTLOOP_CONFORMANCE`, `AGENTLOOP_VERBOSE`, `AGENTLOOP_DESIGN_REVIEW`, and
  `AGENTLOOP_SMOKE_RUN` as booleans (anything not in `{"0","false","no"}` is
  true).

- **`_from_file(config_dir) -> dict`**: reads `.agentloop.toml` from `config_dir`
  (or cwd) via `tomllib`; accepts either flat keys or an `[agentloop]` table.

Precedence summary (highest first): **CLI flags > `.agentloop.toml` > env vars >
built-in defaults.** (The `.env` file, loaded separately by the CLI, only fills
*unset* environment variables — see §5g.)

---

#### `workspace.py` — the sandbox (security boundary)

The only component that touches disk or spawns processes; everything is confined
to one output directory. See §8 for the security discussion.

- **`class WorkspaceError(Exception)`** — raised when an op would escape/violate
  the workspace.

- **`class Workspace`**
  - `__init__(root)`: resolves `root` to an absolute `Path` and `mkdir(parents=
    True, exist_ok=True)`.
  - `resolve(relpath) -> Path`: the guard. Joins `relpath` onto `root` (unless
    already absolute), resolves it, and raises `WorkspaceError` unless the result
    *is* `root` or has `root` among its `.parents`. This rejects `..`
    traversal, absolute paths outside root, and symlink escapes (because
    `.resolve()` follows symlinks before the check).
  - `relpath(path) -> str`: workspace-relative string (used to record
    `files_touched`).
  - `write_file(relpath, content) -> Path`: resolves, creates parent dirs, writes
    UTF-8.
  - `append_file(relpath, content) -> Path`: like write but appends (used for
    `build.log`).
  - `read_file(relpath) -> str`, `exists(relpath) -> bool`.
  - `list_files() -> list[str]`: sorted relative paths of all files under root
    (`rglob("*")`).
  - `run_command(command, *, timeout=300.0) -> CommandResult`: runs `command`
    with `shell=True`, `cwd=self.root`, capturing stdout/stderr as text. On
    `TimeoutExpired` returns a `CommandResult` with `exit_code=124`,
    `timed_out=True`, and a `[timed out after Ns]` note appended to stderr.

Note: `CommandResult` is imported from `engines.base` (shared value type).

---

#### `report.py` — run reporting

- **`@dataclass(slots=True) class StageReport`**: `name: str`, `ok: bool`,
  `detail: str = ""`, `files_touched: list[str] = []`.

- **`@dataclass(slots=True) class RunReport`**: the outcome of a full run.

  | Field | Type | Meaning |
  |---|---|---|
  | `spec_title` | `str` | From `spec.title` |
  | `engine`, `model` | `str` | Resolved config |
  | `stages` | `list[StageReport]` | One per stage |
  | `tests_passed` | `bool` | Final test-loop result |
  | `iterations_used` / `max_iterations` | `int` | Test-fix loop budget usage |
  | `design_approved` | `bool \| None` | `None` if the design stage was skipped |
  | `design_issues` | `list[dict]` | Remaining blocking design issues |
  | `design_iterations` | `int` | Design review→revise cycles run |
  | `smoke_passed` | `bool \| None` | `None` if the smoke stage was skipped |
  | `smoke_iterations` | `int` | Smoke-run→coder-fix cycles run |
  | `conformant` | `bool \| None` | `None` if the conformance stage was skipped |
  | `conformance_issues` | `list[dict]` | Remaining blocking conformance issues |
  | `conformance_iterations` | `int` | Review→fix cycles run |

  - `ok` (property): `all(stage.ok) and tests_passed and conformant is not False
    and design_approved is not False and smoke_passed is not False`. Note the
    deliberate `is not False`: a *skipped* design/smoke/conformance (`None`) does
    not fail the run, but a `False` verdict does.
  - `stopped_at_design_gate` (property): `design_approved is False and not
    tests_passed` — True when the design gate blocked the build before any code
    (and hence any test run) happened.
  - `add_stage(stage)`: append.
  - `to_markdown() -> str`: renders `report.md` — a header block (engine, model,
    **design approved** + cycle count, tests-passed, iterations, **smoke run
    (app starts)** label + fix-cycle count, spec-conformant label + cycle count,
    overall SUCCESS/INCOMPLETE), a per-stage section (✅/❌
    + detail + files touched), a **gate-stop note** when
    `stopped_at_design_gate`, and then "Remaining design issues" and "Remaining
    conformance issues" lists if either is non-empty.

- **`_verdict_label(value) -> str`**: `None`→`"skipped"`, else `"yes"`/`"no"`.
  Used for both the design and conformance verdicts. `_conformance_label` is a
  backwards-compatible alias (`_conformance_label = _verdict_label`).

---

#### `orchestrator.py` — the conductor

Sequences the pipeline and owns all four loops (design, test-fix, smoke,
conformance).
It never calls the model directly; it talks only to agents and the workspace.

- **`ProgressFn = Callable[[str, str], None]`** and **`_noop`** — an optional
  `(stage, message)` progress callback (the CLI passes one that prints via
  `rich`).

- **`class Orchestrator`**
  - `__init__(config, *, progress=None, run_log=None)`. `run_log` is the path to
    the detailed run log (`<out>/run.log`, set by the CLI).
  - `_emit(text)`: append a `[YYYY-MM-DD HH:MM:SS] text` line to `run_log` (when
    set). This is the always-on observation stream, independent of `--verbose`.
  - `progress(stage, message)`: notify the CLI callback AND `_emit` the line.
  - `_log(ws, text)` / `_log_agent(ws, stage, result)`: transcript helpers. They
    always `_emit` to the run log, and additionally — when `config.verbose` —
    append to `<out>/build.log`: either a raw line, or a formatted stage block
    listing each `ToolCall` (`[ok]`/`[ERR] name: summary`) and the agent's final
    message.
  - `_emit_result(report)`: write the final `BUILD RESULT: SUCCESS/INCOMPLETE |
    design_approved=… tests_passed=…(x/y) smoke_passed=… conformant=…` line.

  - **`async build(spec, workspace) -> RunReport`** — top-level control flow:
    1. Build the `AgentContext` (engine, config, workspace, spec, global_spec) and
       the `RunReport`; the registry (`self._agents`/`self._gates`) was loaded in
       `__init__` from the manifest (+ `agent_defs_dir`).
    2. If verbose, truncate/start a fresh `build.log`.
    3. **Stage loop** over `_STAGE_NAMES` (design, code, test, smoke, deploy,
       conformance). For each `name`:
       - run `pre_<name>` declarative gates (`_run_gates`) — a blocking pre-gate
         stops the build (finalize + return);
       - `halt = await _stage_<name>(ctx, report)` — the per-stage body (each
         returns True only to **halt**: the design gate returns `not approved`, so
         an unapproved design stops before any code, as before);
       - if `halt` → finalize + return;
       - if `_stop_after(name)` → set `report.stopped_after` + finalize + return;
       - run `post_<name>` declarative gates.
    4. `_finalize` (emit `BUILD RESULT`, write `report.md`); return report.
    The `_stage_*` methods hold each stage's Python (design gate / coder / test
    loop / smoke loop / deployer / conformance loop). Placements are derived from
    the stage names, so declarative gates attach without hard-coded hooks.

    **Partial runs (`--stop-after`):** after each of the design, code, test,
    smoke, and deploy stages, `_stop_after(stage)` checks `config.stop_after`; if
    it matches, it sets `report.stopped_after`, logs a "stopping after …" progress
    line, and returns via `_finalize(report, workspace)` (emit `BUILD RESULT:
    STOPPED after <stage>` + write `report.md`). A deliberate stop is not a
    failure — `RunReport.ok` drops the "tests_passed" requirement when
    `stopped_after` is set (relying on the ran-stage `ok` flags). e.g.
    `--stop-after design` runs the architect+critic gate and stops once approved,
    before any code is written. All exits (hard-gate reject, each stop point, and
    the normal end) go through the shared `_finalize`.

  - **`async _design_loop(ctx, report) -> bool`** — the design gate:
    - `architect.design(ctx)` → model writes `design.md`; the verdict is obtained
      via `_reviewed_verdict(...)` (see below), which runs `critic.review(ctx)`,
      parses `design_review.json`, and — if unparseable — retries the review ONCE
      with a JSON-only nudge before giving up.
    - Loop: `while verdict is not None and not verdict["approved"] and
      _has_blocking(verdict) and iterations < config.max_design_iterations:` bump
      the counter, `architect.revise(ctx, current_issues, history=…)` (model
      edits `design.md`), `critic.review(ctx)` again, re-parse. A `None` re-parse
      `break`s (keep the last verdict).
    - **Cumulative issue history (anti-regression):** the loop keeps a deduped
      `seen` set of every blocking issue raised across all cycles (`_remember_issues`
      / `_issue_key`). Each revise gets the *current* issues **and** the earlier
      ones (`history`), and `DESIGN_REVISE` tells the architect to output the
      COMPLETE design preserving already-correct sections verbatim and NOT
      reintroduce earlier issues. Because the OpenAI-compatible engines only have
      `write_file` (full overwrite, no patch tool), a stateless revise otherwise
      re-drops sections it had fixed (e.g. a diagram) — this history curbs that
      oscillation.
    - Each cycle's verdict is recorded via `_record_design_verdict(ws, cycle,
      verdict)`: it appends `{cycle, approved, issues}` to
      `design_review.history.jsonl` (always — so **rejected** issues survive even
      though `design_review.json` is overwritten each review) and logs a
      `design verdict (cycle N): …` line to `build.log` when verbose.
    - `report.design_iterations = iterations`.
    - If `verdict is None` after the retry, behavior depends on `config.strict_gate`:
      - **strict** → set `design_approved = False`, append a failing `design`
        stage, **return `False`** (blocks coding — treat "no verdict" as a reject).
      - **lenient (default)** → **fail open**: `_emit` a loud WARNING, record a
        `design` stage (`ok = exists("design.md")`), and **return `True`**.
    - Otherwise set `report.design_approved` and `report.design_issues`
      (blocking only), append a `design` stage (`ok = design_approved`), and
      **return `report.design_approved`** — the caller uses this to decide
      whether coding proceeds.

  - **`async _test_loop(ctx, report)`**:
    - `tester.write_tests(ctx)`; run `run = workspace.run_command(test_cmd)`.
    - Loop: `while not run.ok and iterations < config.max_iterations:` bump the
      counter, `coder.fix(ctx, run.combined_output)` (the CODER, not the tester,
      fixes the source using the error output), re-run the command.
    - `report.tests_passed = run.ok`; `report.iterations_used = iterations`;
      append a `tester` stage whose detail includes the final exit code and the
      last 1500 chars of output.
    - **Pass/fail is `run.ok` = `exit_code == 0 and not timed_out`** — a
      deterministic subprocess fact, never the model's claim.

  - **`async _smoke_loop(ctx, report)`** (runs after `_test_loop`, gated on
    `config.smoke_run`): proves the built app *actually runs*, catching runtime
    failures the unit tests miss.
    - `smoke.write_check(ctx)` → model writes `smoke_check.sh`.
    - **Write guard** (weaker models sometimes *print* the script instead of
      saving it), in order:
      1. `_recover_smoke_script(ws, result)` — if the file is absent but the
         message contains a script (a fenced ```bash block, or text starting with
         a shebang, via `_extract_script`), write it to `smoke_check.sh` and log
         the recovery.
      2. If still absent, retry once with `smoke.write_check(ctx,
         nudge=SMOKE_WRITE_NUDGE)` and attempt recovery from that message too.
      3. If STILL absent, **fail loudly** — `_emit` a `FAIL` line, set
         `report.smoke_passed = False`, append a failing `smoke` stage, return.
         (An app we can't even attempt to run is a real failure, so `report.ok`
         becomes `False` — no more silent skip.)
    - Otherwise `run = workspace.run_command("bash smoke_check.sh", timeout=120)`.
      Loop: `while not run.ok and iterations < config.max_smoke_iterations:` bump
      the counter, `coder.fix(ctx, "<smoke failed>\n" + run.combined_output)` (the
      **coder**, which holds the design context, fixes the source from the smoke
      error), re-run the check.
    - `report.smoke_passed = run.ok`; `report.smoke_iterations = iterations`;
      append a `smoke` stage whose detail includes the final exit code. As with
      the test loop, pass/fail is a deterministic subprocess fact.

  - **`async _conformance_loop(ctx, report)`**:
    - The verdict is obtained via `_reviewed_verdict(...)` (runs `agent.review`,
      parses `conformance.json`, retries once with a JSON-only nudge if needed).
    - If no parseable verdict after the retry: **strict** → set
      `conformant = False` + failing stage; **lenient (default)** → loud WARNING +
      non-blocking stage (`ok=True`, "skipping review") and return.
    - Loop: `while not verdict["conformant"] and _has_blocking(verdict) and
      iterations < config.max_conformance_iterations:` bump counter,
      `agent.fix(ctx, json.dumps(verdict["issues"]))`, **re-run tests** (to catch
      regressions the fix introduced, updating `report.tests_passed`),
      `agent.review(ctx)` again, re-parse. If a re-review yields no parseable
      verdict, `break` (keep the last good verdict).
    - Record `report.conformant`, `conformance_issues` (blocking only),
      `conformance_iterations`, and a `conformance` stage.

  - **`async _reviewed_verdict(ctx, review, filename, key, *, stage, label)`**:
    the retry wrapper both critics go through. It calls `review()` (a
    `lambda nudge=None: critic.review(ctx, nudge=nudge)`), obtains the verdict via
    `_verdict_from`, and if that is `None`, calls `review(nudge=…)` ONCE more with
    `prompts.VERDICT_JSON_NUDGE` (appended to the task, asking for JSON only) and
    tries again. Returns `(verdict_or_None, last_result)`.
  - **`_verdict_from(workspace, result, filename, key, stage) -> dict | None`**:
    parses the written file (`_read_verdict`) **and, if that's `None`, falls back
    to the agent's final message** (`_parse_verdict(result.text, key)`). Weaker/
    local models frequently emit a valid verdict as their message but never call
    the write tool; this recovers it (and logs "verdict recovered from the agent's
    message"). This single fallback is what lets local models clear the gate.
  - **`_read_verdict(workspace, filename, key) -> dict | None`**: reads the file
    (or `None` if missing) and delegates to `_parse_verdict`. Used by both loops.
  - **`_parse_verdict(raw, key) -> dict | None`** (module helper): the lenient
    parser. `key` is the boolean the verdict must contain — `"approved"` for
    design, `"conformant"` for conformance. Strips accidental ```` ``` ```` fences,
    tries `json.loads` on the whole string, then on the first-`{`…last-`}` slice
    (so JSON embedded in prose/a printed message still parses). Returns `None` on
    failure, non-dict, or missing `key`; ensures `issues` is a list.

- **Module helpers** (reused by both the design and conformance loops):
  - `_blocking_issues(verdict) -> list[dict]`: issues whose `severity` (lowered)
    is `"high"` or `"medium"`. **This is the gate** — low-severity issues never
    trigger a revise/fix cycle.
  - `_has_blocking(verdict) -> bool`: truthiness of the above.
  - `_has_source(workspace)`: any file present other than `design.md`/`report.md`.
  - `_has_deploy_artifact(workspace)`: any filename containing `dockerfile`,
    `deploy.sh`, `deploy.md`, or `docker-compose.yml` (case-insensitive).

---

#### `layered_spec.py` — three-layer composable specs

Runs **before** the pipeline with **no LLM**. Loads three layers and
deterministically renders one effective multi-tenant spec. See §5f for the
example.

- **`DIRECTIVES = ("extend", "override", "disable", "add")`**.
- **`class LayeredSpecError(Exception)`** — missing/malformed files or bad
  directives.

Dataclasses (all `slots=True`):

| Class | Fields |
|---|---|
| `Stack` | `name: str`; `language="python"`; `backend/frontend/database/tenancy/test_command: str\|None`; `extra: dict` |
| `Feature` | `id: str`, `name: str`, `body: str` |
| `Override` | `feature: str`, `directive: str`, `rules: str` |
| `CustomerLayer` | `customer: str`, `tenant_id: str`, `overrides: list[Override]` |
| `LayeredProject` | `stack: Stack`, `features: list[Feature]`, `customers: list[CustomerLayer]`; `feature_ids() -> set[str]` |
| `ComposedSpec` | `text: str`, `title: str`, `language: str`, `test_command: str\|None` |

Loading:

- **`load_project(project_dir) -> LayeredProject`**: validates the dir exists,
  then `_load_stack` + `_load_features` + `_load_customers`.
- **`_load_stack(root)`**: reads `stack.yaml` (required — missing → error);
  requires a mapping; pulls the known keys into `Stack` and stuffs any *unknown*
  keys into `Stack.extra` (rendered later as extra bullets). `name` defaults to
  the directory name.
- **`_load_features(root)`**: reads `features/*.md` (dir required, at least one
  file required). Each file is split via `_parse_frontmatter`; `id`/`name`
  default to the file stem. **Duplicate feature ids are a hard error.**
- **`_load_customers(root)`**: `customers/` is *optional* (absent → single-tenant
  project). Reads `*.yaml`/`*.yml`; each must be a mapping. `customer`/`tenant_id`
  default to the file stem. Each override must be a mapping with a valid
  `directive` (else error) and a non-empty `feature` (else error); `rules` is
  stripped.
- **`_parse_frontmatter(path) -> (meta, body)`**: if the file starts with `---`,
  finds the closing `\n---`, YAML-parses the block into `meta`, returns the rest
  as the body; otherwise returns `({}, raw)`.

Composition:

- **`compose(project) -> ComposedSpec`**: calls `_validate`, then builds the
  Markdown as a list of lines:
  - `multi_tenant = bool(project.customers)`; title gets a
    `" — Multi-Tenant Application"` suffix only when multi-tenant.
  - **Tech Stack** section: language + any of backend/frontend/database that are
    set + `stack.extra` items.
  - **Tenancy** section (multi-tenant only): lists each tenant with its id,
    states the tenant-resolution rule (`stack.tenancy`), and adds a strict
    data-isolation requirement.
  - Groups overrides by feature id (`by_feature`) and collects `add` directives
    separately (`added`).
  - **Global Features**: each feature's name/id/body, followed by a "Per-tenant
    variations" bullet list for any overrides targeting it — each rendered as
    `**Customer** (\`tenant_id\`) — _directive_: <one-lined rules>`.
  - **Tenant-specific features**: each `add` directive rendered as a feature
    available only to that tenant.
  - **Cross-cutting requirements**: a fixed block requiring a test suite per
    feature/variation, per-tenant seed data, a deploy artifact + DEPLOY.md, and
    a `README.md` (what the project is, prerequisites, copy-pasteable
    install/run commands, and 1-2 example requests).
  - Returns `ComposedSpec(text, title, language=stack.language,
    test_command=stack.test_command)`.
- **`_validate(project)`**: every non-`add` override must target a **known**
  feature id, else `LayeredSpecError` (suggesting `add` for new features).
- **`_oneline(text)`**: collapses whitespace (`" ".join(text.split())`) so a
  multi-line YAML block renders as one bullet.

Determinism: features are loaded in sorted filename order, customers in sorted
order, and composition is pure string assembly — so `compose(p).text ==
compose(p).text` (asserted in tests).

---

#### `prompts/*.md` — role prompts (loaded by `prompts.py`)

One deliberately-terse `.md` file per prompt (state the goal, not an
over-prescriptive procedure), loaded/`${var}`-interpolated by `prompts.py`. The
files below and their template `${...}` vars:

| File | Role | Vars | Key instructions |
|---|---|---|---|
| `architect.md` | Architect (design) | — | Given a BRD (no schema/endpoints), **derive** the technical design and write `design.md` only — summary, tech stack, data model/schema, API endpoints, UI screens, key flows, **Mermaid diagrams** (component/architecture, data-flow, a `sequenceDiagram` per key flow, `erDiagram`), non-functional handling, project layout, requirement traceability. Uses the mandated stack from the global spec if provided. Make concrete choices; no code, no TBDs. |
| `design_revise.md` | Architect (revise) | `${spec}`, `${issues}`, `${history}` | Resolve current high/medium issues without regressing: output the COMPLETE design, preserve correct sections verbatim, keep earlier (`${history}`) issues fixed; no code. |
| `design_review.md` | Design critic | — | Review `design.md` against the BRD (coverage, data model, API/interface, non-functional, soundness, **idiomatic & simple**); write **only** the exact `design_review.json`; `approved=true` only when no high/medium issues; don't modify `design.md`. The idiomatic check flags (**high** severity) unnecessary custom abstractions/wrappers that reimplement framework features and over-engineering. |
| `coder.md` | Coder | — | Read `design.md` (an **approved** design) and implement it **exactly**; no redesign, no TODOs/stubs; include manifests; no tests, no deploy. |
| `tester_write.md` | Tester (write) | `${test_command}` | Write a thorough suite, run it once with `${test_command}`; fix real *source* bugs; never weaken tests. |
| `coder_fix.md` | Coder (fix) | `${test_command}`, `${test_output}` | Coder reads the error, re-reads `design.md` + failing source, fixes the source; don't re-run. |
| `conformance_review.md` | Reviewer | — | Grade against the **spec text itself**, not the passing tests; write **only** the exact `conformance.json`. |
| `conformance_fix.md` | Fixer | `${test_command}`, `${spec}`, `${issues}` | Resolve high/medium issues, keep tests passing. |
| `deployer.md` | Deployer | — | Produce a spec-appropriate deploy artifact + `DEPLOY.md` (+ README when the spec asks); don't touch source/tests. |
| `smoke.md` | Smoke tester | — | Write **only** a self-contained `smoke_check.sh` proving the app runs end-to-end; free non-5000 port, real-200 readiness; fast/self-terminating; don't run it. |
| `verdict_json_nudge.md` | (retry) | `${filename}`, `${key}` | Re-request a valid JSON verdict when the critic's output wasn't parseable. |
| `smoke_write_nudge.md` | (retry) | — | Re-request that the smoke agent actually *write* `smoke_check.sh`. |

The task string for each action lives in `agents.yaml` (also `${var}`-templated);
the shared **template vars** are `spec, language, test_command, global, issues,
history, test_output, nudge, filename, key`. Interpolation is `string.Template`
`safe_substitute`, so literal JSON/shell braces in the prompts are left intact.

The `DESIGN_REVIEW` and `CONFORMANCE_REVIEW` prompts pin the exact JSON shapes:

```json
{"approved": <true|false>, "issues": [{"requirement": "...", "severity": "high|medium|low", "detail": "..."}]}
{"conformant": <true|false>, "issues": [{"requirement": "...", "severity": "high|medium|low", "detail": "..."}]}
```

and both instruct the boolean to be `true` only when there are no high/medium
issues — which mirrors the orchestrator's `_blocking_issues` gate.

---

#### `cli.py` — the `agentloop` command

Click-based CLI. `main` is the group; three commands hang off it.

- **`_load_dotenv(path=".env")`**: minimal dependency-free `.env` loader. Reads
  `KEY=VALUE` lines (skips blanks/comments/lines without `=`), strips surrounding
  quotes, and sets the var **only if unset** (`key not in os.environ`) — so a
  real shell export always wins. Called by `main()` on every invocation.

- **`main()`** (`@click.group`, with `--version`): the group callback runs
  `_load_dotenv()`.

- **`build_options(func)`**: a decorator bundling the flags shared by `build` and
  `build-project` (see §7 for the full table). Flags default to `None` so unset
  flags don't override config (matching `AppConfig.resolve`).

- **`_effective_model(opts) -> str | None`**: if no `--model` and engine is
  `azure`, defaults the model to `AZURE_OPENAI_DEPLOYMENT_NAME` so the
  report/transcript name the real deployment.

- **`_resolve_config(opts, *, language, test_command) -> AppConfig`**: builds the
  overrides dict (using `_effective_model`) — including `design_review`,
  `max_design_iterations`, `smoke_run`, and `max_smoke_iterations` alongside the
  conformance/verbose/etc. options — and calls `AppConfig.resolve`.

- **`_slug(text) -> str`**: lowercases and hyphenates to a filesystem-safe
  project name (falls back to `"project"`).

- **`_resolve_out(opts, default_name) -> str`**: resolves the output directory.
  Explicit `--out` wins; otherwise returns `<--workspace>/<name>` where name is
  `--name` (slugged) or the command-derived `default_name`.

- **`_print_config(spec, config, out_dir)`**: prints the resolved plan via
  `rich`, including a line for **design review** (`on`/`off`, with the max-cycle
  count when on), **smoke run** (`on`/`off`), and **conformance** (same). For
  `local`, also prints the base URL and warns if a Claude model id was left set
  with `--engine local`.

- **`_run_build(spec, config, out_dir, debug)`**: shared execution — print
  config; if `dry_run`, stop before any LLM call; else create the `Workspace`,
  build an `Orchestrator` with a printing progress callback, `asyncio.run(
  orchestrator.build(...))`. On exception at this CLI boundary it prints
  `Type: message` and `sys.exit(1)` (unless `--debug`, which re-raises). Prints
  the SUCCESS/INCOMPLETE summary; a **design-approved** line (yes/no + cycles)
  when the design stage ran; a **gate-stop line** ("Build stopped at the design
  gate — no code was generated.") when `stopped_at_design_gate`; tests-passed +
  iterations; a **smoke run (app starts)** line (yes/no + fix cycles) when the
  smoke stage ran; the conformance summary; and the report path. Exits `1` if
  `not report.ok`.

- **`build(spec_path, **opts)`** (`@main.command`): loads the flat spec-or-BRD
  (`SpecError` → exit 2); derives the default project name (the input's **folder
  name** when the file is a bare `spec.md` **or** `brd.md`, else the file stem)
  and resolves the output dir via `_resolve_out`; language = `--language` or
  `spec.language_hint()`; resolve config; run.

- **`build_project(project_dir, **opts)`** (`@main.command("build-project")`):
  `compose(load_project(project_dir))` (`LayeredSpecError` → exit 2); default
  project name = the project dir's basename → `_resolve_out`; wraps the composed
  text via `SpecDocument.from_text`; language/test_command fall back to the
  stack-derived values; resolve config; run.

- **`compose_cmd(project_dir, out_path)`** (registered as `compose`): composes and
  either writes `--out` or `click.echo`es the raw text to stdout (no rich markup,
  so it pipes cleanly). Registered under the name `compose` via
  `main.add_command(compose_cmd, name="compose")` (the function name avoids
  shadowing the imported `compose`).

Exit codes: `0` success; `1` build ran but incomplete / runtime error; `2` bad
input (spec or layered-spec error).

---

### 4.2 Engine layer

#### `engines/__init__.py`

Re-exports the value types and the protocol (`AgentResult`, `CommandResult`,
`Engine`, `ToolCall`) plus registry helpers (`available_engines`, `get_engine`).

#### `engines/base.py` — the seam and its value types

- **`@dataclass(slots=True) class ToolCall`**: `name: str`, `summary: str`,
  `ok: bool = True`. A log entry for one tool invocation.

- **`@dataclass(slots=True) class CommandResult`**: `command`, `exit_code`,
  `stdout`, `stderr`, `timed_out=False`.
  - `ok` (property): `exit_code == 0 and not timed_out` — the canonical "did it
    pass" fact used across the codebase.
  - `combined_output` (property): stdout + stderr joined and stripped.

- **`@dataclass(slots=True) class AgentResult`**: what an engine returns per turn.
  - `text: str` (final natural-language output),
  - `files_touched: list[str]` (workspace-relative),
  - `tool_calls: list[ToolCall]`,
  - `stop_reason: str = "end_turn"` (`end_turn` / `max_iterations` / `refusal` /
    …).

- **`@runtime_checkable class Engine(Protocol)`**: `name: str` attribute plus one
  method:
  ```python
  async def run_agent(self, *, system_prompt: str, task: str, workspace: Path,
                      tools: Sequence[str], model: str, effort: str) -> AgentResult
  ```
  The docstring makes the sandbox contract explicit: implementations **MUST**
  confine all file/command access to `workspace`. This one method is the entire
  surface the rest of the framework depends on.

#### `engines/registry.py` — name → factory

- `_FACTORIES: dict[str, Callable[[], Engine]]` — lazily-constructed factories so
  selecting one engine never imports another's optional deps.
- `register(name, factory)`, `available_engines() -> sorted list`,
  `get_engine(name) -> Engine` (raises `ValueError` listing available engines on
  a miss).
- `_make_claude_api` / `_make_agent_sdk` / `_make_local` / `_make_azure`: each
  imports its adapter *inside the function* and constructs it. Registered at
  import time under `claude_api`, `agent_sdk`, `local`, `azure`.

#### `engines/_openai_common.py` — shared OpenAI function-calling loop

Both `local` and `azure` speak OpenAI chat-completions + function calling; only
client construction differs. This module owns the loop and the workspace-backed
tools.

- **`_MAX_TURNS = 60`** — hard ceiling so a misbehaving agent can't spin forever.

- **`TOOLS`** — five OpenAI function definitions (the **generic tool names** the
  model sees for these backends): `run_bash(command)`, `write_file(path,
  content)`, `read_file(path)`, `str_replace(path, old_str, new_str)`,
  `list_files()`.

- **`async run_openai_tool_loop(client, *, model, system_prompt, task, workspace)
  -> AgentResult`**:
  - Wraps `workspace` in a `Workspace`; seeds `messages` with system + user(task).
  - Loops up to `_MAX_TURNS`: `client.chat.completions.create(model, messages,
    tools=TOOLS, tool_choice="auto")`. If the reply has no `tool_calls`, break
    (record final text). Otherwise append the assistant message (echoing the
    `tool_calls`), then for each call run `_dispatch`, log a `ToolCall`, and
    append a `role:"tool"` result message. If the `for` exhausts without
    breaking, `stop_reason = "max_iterations"`.
  - Returns `AgentResult(text, sorted(files_touched), tool_calls_log,
    stop_reason)`.

- **`_dispatch(ws, tool_call, files_touched) -> (text, ok)`**: parses JSON args
  (bad JSON → error string) and executes:
  - `run_bash` → `ws.run_command(...)` (returns combined output + `.ok`),
  - `write_file` → `ws.write_file`, records `files_touched`,
  - `read_file` → `ws.read_file`,
  - `str_replace` → reads the file, requires **exactly one** match of `old_str`
    (else error), writes the replacement,
  - `list_files` → `ws.list_files()`.
  - Catches `WorkspaceError` (sandbox violation), `KeyError` (missing arg), and
    any other exception, surfacing each as an `error: ...` string back to the
    model (so it can self-correct) with `ok=False`.

#### `engines/claude_api.py` — raw Anthropic adapter (default)

Dependency-light (only `anthropic`); a hand-rolled tool loop over the
Anthropic-defined, schema-less **bash** and **text-editor** tools.

- `_BASH_TOOL = {"type": "bash_20250124", "name": "bash"}`; `_EDITOR_TOOL =
  {"type": "text_editor_20250728", "name": "str_replace_based_edit_tool"}`;
  `_MAX_TURNS = 60`.
- **`class ClaudeAPIEngine`** (`name = "claude_api"`): `__init__` guards that
  `anthropic` is importable (clear `RuntimeError` if not).
  - **`async run_agent(...)`**: creates `anthropic.AsyncAnthropic()`; loops up to
    `_MAX_TURNS`, each turn calling `client.messages.stream(model,
    max_tokens=32000, system=system_prompt, thinking={"type":"adaptive"},
    output_config={"effort": effort}, tools=[bash, editor], messages=messages)`
    and awaiting `get_final_message()`. Handles `stop_reason`: `refusal` → break;
    anything other than `tool_use` → break; on `tool_use`, echoes the assistant
    turn (including thinking + tool_use blocks) back into `messages`, dispatches
    each `tool_use` block, and appends a `user` turn of `tool_result` blocks
    (with `is_error`). Falls through to `max_iterations` if the loop exhausts.
- **`_extract_text`**: joins all `text` blocks. **`_summarize`**: short label per
  tool call. **`_dispatch_tool`**: routes `bash` → `_run_bash`, editor →
  `_run_editor`; catches `WorkspaceError`/any exception into an error string.
- **`_run_bash`**: handles `restart`; empty command → error; else
  `ws.run_command`.
- **`_run_editor`**: implements the text-editor tool commands: `view` (dir →
  list; file → content, honoring `view_range`), `create` (write + record),
  `str_replace` (requires exactly one match; 0 → not found, >1 → ambiguous),
  `insert` (insert a line at `insert_line`). Records `files_touched` for
  create/replace/insert.

Note the effort/thinking wiring: this adapter is the one that actually passes
`effort` and adaptive thinking to the model; the OpenAI-based adapters ignore
`effort` (no such knob).

#### `engines/agent_sdk.py` — Claude Agent SDK adapter (least code)

Delegates the loop, tool execution, and sandboxing to `claude-agent-sdk`
(optional dependency).

- `_TOOL_NAME_MAP`: our **generic** names → SDK/Claude Code names (`bash`→`Bash`,
  `read`→`Read`, `write`→`Write`, `edit`→`Edit`, `glob`→`Glob`, `grep`→`Grep`).
- **`class AgentSDKEngine`** (`name = "agent_sdk"`): `__init__` guards the import.
  - **`async run_agent(...)`**: maps tool names, builds `ClaudeAgentOptions(
    system_prompt, allowed_tools=allowed, cwd=<resolved workspace>, model,
    permission_mode="acceptEdits")`, then iterates `query(prompt=task,
    options=...)`. For each `AssistantMessage` it collects `TextBlock` text and
    `ToolUseBlock` calls (recording `files_touched` for `Write`/`Edit` via
    `_touched_path`); `ResultMessage.subtype` becomes the `stop_reason`.
- Helpers `_summarize` and `_touched_path` mirror the others.

Because the SDK owns the loop and sandbox, this adapter is the thinnest.

#### `engines/local.py` — OpenAI-compatible local models

- `_DEFAULT_BASE_URL = "http://localhost:11434/v1"` (Ollama).
- **`class LocalEngine`** (`name = "local"`): `__init__` guards `openai` is
  importable and reads `AGENTLOOP_BASE_URL` (default above) and
  `AGENTLOOP_API_KEY` (default `"ollama"` — most local servers ignore it).
  - **`async run_agent(...)`**: builds `AsyncOpenAI(base_url, api_key)` and
    delegates to `run_openai_tool_loop`. `effort` is accepted but unused (no such
    knob in the OpenAI API).

Caveat (from the README): the model **must support tool/function calling**; small
models are unreliable on the multi-step loop.

#### `engines/azure_openai.py` — Azure OpenAI

Same shared loop; Azure differs by needing an endpoint + api-version, and the
"model" argument is the **deployment name**.

- **`class AzureOpenAIEngine`** (`name = "azure"`): `__init__` guards `openai`,
  then reads (with fallbacks) `AZURE_OPENAI_ENDPOINT` (or `ENDPOINT_URL`),
  `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_API_VERSION` (or `OPENAI_API_VERSION`),
  and `AZURE_OPENAI_DEPLOYMENT_NAME`. Any missing var raises a `RuntimeError`
  naming exactly what's missing.
  - **`async run_agent(...)`**: builds `AsyncAzureOpenAI(azure_endpoint, api_key,
    api_version)`. Chooses the deployment: use the passed `model` if it's set and
    doesn't start with `claude`, else fall back to the configured deployment.
    Delegates to `run_openai_tool_loop`.

---

### 4.3 Agents (data: `agents.yaml` manifest + `prompts/*.md` + a loader)

Agents are **data**, not code. `prompts/*.md` hold the prompt text; `agents.yaml`
maps each action to a role + prompt file + task template + tools; `agents.py` is a
thin loader + runner. A project can add/override all of this via an
`agent_defs_dir` — no Python.

- **`prompts.py`** (loader): `load(name, extra_dir=None)` reads
  `<extra_dir>/prompts/<name>.md` then the packaged `prompts/<name>.md` (cached);
  `render(name, extra_dir, **vars)` = `string.Template(text).safe_substitute(vars)`.
  Using `${var}` **safe-substitution** means literal `{...}`/`%{...}`/`$(...)` in
  the JSON/shell examples are left untouched (this killed the old brace-escaping
  fragility). Vars: `spec, language, test_command, global, issues, history,
  test_output, nudge, filename, key`.
- **`agents.yaml`** — `agents:` map of `action -> {role?, prompt, task, tools?}`
  (role defaults to the action id up to `:`; tools default to `DEFAULT_TOOLS`),
  plus a `gates:` list. Built-in actions: `architect`, `architect:revise`,
  `design_critic`, `coder`, `coder:fix`, `tester`, `smoke`, `deployer`,
  `conformance`, `conformance:fix`.
- **`agents.py`**: `AgentContext`, `@dataclass AgentSpec(role, prompt, task, tools,
  extra_dir)`, `@dataclass GateSpec(stage, placement, generator, critic, reviser?,
  verdict_file, verdict_key, history_file?, max_iterations, blocking)`.
  - `load_registry(agent_defs_dir=None) -> (dict[action, AgentSpec], [GateSpec])`:
    parse the package manifest, then merge `<agent_defs_dir>/agents.yaml` over it
    (agents override/add by id; gates append).
  - `run_agent(ctx, spec, **kw)`: render prompt + task, **append `nudge`
    generically** when present, call `engine.run_agent(...)`. The only place agent
    LLM I/O happens. `_truncate` (for `coder:fix` test output) lives here.

The orchestrator loads the registry once (`self._agents`, `self._gates`) and drives
each turn via `_run(base_ctx, action, **kw)` — scope to the action's `role`
(per-agent model via `_agent_ctx`), then `run_agent(spec)`. Fixing failures is
always the **coder** (`coder:fix`).

#### Adding a new agent / gate (e.g. Security Agent + Security Critic) — no Python
Create an `agent_defs_dir` (point at it with `--agent-defs-dir` /
`AGENTLOOP_AGENT_DEFS_DIR`):
1. `agent_defs_dir/prompts/security.md`, `security_review.md`.
2. `agent_defs_dir/agents.yaml`:
   ```yaml
   agents:
     security:        {prompt: security, task: "Review the security of ${spec}"}
     security_critic: {prompt: security_review, task: "...write security_review.json..."}
   gates:
     - {stage: security, placement: post_smoke, generator: security,
        critic: security_critic, verdict_file: security_review.json,
        verdict_key: approved, blocking: false}
   ```
3. Optionally `[agentloop.agents.security]` in `.agentloop.toml` to route it to a
   model. That's it — the orchestrator runs the gate via `_critique_gate` at the
   named `placement`.

---

## 5. Key flows / sequences

### (a) A single agent turn — how a file gets written via tool calls

Using the coder stage with an OpenAI-based engine:

1. A `_stage_*` calls `self._run(ctx, "coder")` (scopes to the coder's per-agent
   model, then `agents.run_agent(scoped_ctx, spec)`).
2. `run_agent` renders `spec` (prompt `coder.md` + task template) and calls
   `ctx.engine.run_agent(system_prompt=…, task=…, workspace=ctx.workspace.root,
   tools=DEFAULT_TOOLS, model, effort)`.
3. `run_openai_tool_loop` sends `{system, task, TOOLS}` to the model.
4. The model replies with a `tool_calls` list, e.g.
   `write_file(path="app.py", content="…")`.
5. `_dispatch` maps that to `Workspace.write_file("app.py", "…")` — **the file
   now exists in `--out`** — and records it in `files_touched`. A
   `role:"tool"` result ("wrote app.py") is appended to the conversation and a
   `ToolCall` is logged.
6. Steps 4–5 repeat for every file. When the model returns a message with **no
   tool calls**, the turn ends and `run_agent` returns an `AgentResult` listing
   everything written.

The model authored the *content*; the Engine+Workspace did the *writing*. (With
`claude_api` the tools are `bash`/`str_replace_based_edit_tool`; with `agent_sdk`
the SDK performs the writes itself.)

### (b) The design-review loop — the hard gate

In `Orchestrator._design_loop` (runs **first**, before any code):

```python
await architect.design(ctx)                       # model writes design.md
await critic.review(ctx)                            # model writes design_review.json
verdict = self._read_verdict(ws, "design_review.json", "approved")
iterations = 0
while (verdict is not None and not verdict["approved"]
        and _has_blocking(verdict) and iterations < config.max_design_iterations):
    iterations += 1
    await architect.revise(ctx, json.dumps(verdict["issues"]))  # model edits design.md
    await critic.review(ctx)                                      # re-review
    new = self._read_verdict(ws, "design_review.json", "approved")
    if new is None: break
    verdict = new
report.design_iterations = iterations
# verdict is None -> fail-open (proceed); else report.design_approved gates coding
```

`build()` calls this first; **if it returns `False`** (design rejected within the
budget), the orchestrator writes `report.md` and returns — **no coder, tester, or
deployer runs.** The report's `stopped_at_design_gate` is then True and the gate
note appears in `report.md` and the CLI summary. Only **high/medium** design
issues gate the loop; low-severity findings are reported but never trigger a
revise cycle. A missing/unparseable verdict *fails open* (proceed), so a broken
critic can't wedge the pipeline. With `--no-design-review`, `_design_loop` is
skipped entirely but the architect still writes `design.md` so the coder has a
design to build.

### (c) The test-fix loop — how "tests pass" is decided

In `Orchestrator._test_loop`:

```python
await tester.write_tests(ctx)                 # tester writes tests/ via tools
run = workspace.run_command(test_cmd)          # actually runs e.g. `python -m pytest -q`
iterations = 0
while not run.ok and iterations < config.max_iterations:
    iterations += 1
    await coder.fix(ctx, run.combined_output)  # CODER gets the error, edits source
    run = workspace.run_command(test_cmd)       # re-run, re-check
report.tests_passed = run.ok                     # ok == exit_code 0 and not timed_out
report.iterations_used = iterations
```

Pass/fail is a **deterministic subprocess fact** (`CommandResult.ok`), never the
model's opinion. The loop ends when the process exits 0 *or* the iteration budget
is exhausted (the run is then reported INCOMPLETE).

> Design honesty: the tester writes the tests and the coder fixes the source to
> pass them, so "tests pass" only proves the code matches the pipeline's *reading*
> of the design. That is exactly why the smoke stage exists (proving the app
> actually runs), the conformance stage exists (grading against the *original*
> spec), and the design gate exists (validating the design against the BRD up
> front).

### (d) The smoke loop — does the app actually run?

In `Orchestrator._smoke_loop` (runs after the test-fix loop, gated on
`config.smoke_run`):

```python
await smoke.write_check(ctx)                    # model writes smoke_check.sh
if not workspace.exists("smoke_check.sh"):
    # non-blocking: record ok=True and skip
    ...
run = workspace.run_command("bash smoke_check.sh", timeout=120)
iterations = 0
while not run.ok and iterations < config.max_smoke_iterations:
    iterations += 1
    await coder.fix(ctx, "<the smoke check failed>\n" + run.combined_output)
    run = workspace.run_command("bash smoke_check.sh", timeout=120)
report.smoke_passed = run.ok
report.smoke_iterations = iterations
```

The smoke check *starts and exercises the real app* (a web service in the
background + a real request; a CLI command; a library import+call) and exits
non-zero on any failure — catching runtime bugs the unit tests miss. Pass/fail is
again the deterministic `CommandResult.ok`, never the model's opinion. Failures
are fed back to the **coder** (same `fix` method as the test loop). If no
`smoke_check.sh` is produced, the stage is **non-blocking** (`ok=True`, skipped),
so a missing script never wedges the build.

### (e) The conformance loop — verdict parsing

In `Orchestrator._conformance_loop`:

1. `agent.review(ctx)` → model writes `conformance.json` (graded against the
   **original spec**).
2. `verdict = _read_verdict(ws, "conformance.json", "conformant")` — the same
   lenient parser the design loop uses (missing file → `None`; strips accidental
   code fences and slices `{ … }`; validates it's a dict with the `conformant`
   key; normalizes `issues` to a list).
3. If `verdict is None`: record a **non-blocking** conformance stage and return
   (a broken reviewer never fails the build).
4. Else loop while `not verdict["conformant"]` **and** `_has_blocking(verdict)`
   (a high/medium issue exists) **and** cycles remain:
   - `agent.fix(ctx, json.dumps(verdict["issues"]))` — model edits code,
   - re-run tests (updating `report.tests_passed` to catch regressions),
   - `agent.review(ctx)` again and re-parse (a `None` re-parse breaks the loop,
     keeping the last verdict).
5. Record `report.conformant`, blocking `conformance_issues`, and the cycle
   count.

Only **high/medium** issues gate the loop; low-severity findings are reported but
never trigger a fix.

### (f) Layered-spec load + compose (illustrative example)

The `build-project` layered feature is live in code (`layered_spec.py`), but no
example ships in `specs/`. The walkthrough below uses an illustrative
multi-tenant to-do directory to show how the three layers compose:

- **Layer 1 — `stack.yaml`**: `name: Multi-Tenant To-Do`, `language: python`,
  `backend: FastAPI …`, `database`, `tenancy` (X-Tenant-ID header, unknown/missing
  → HTTP 400), and a `test_command` that installs FastAPI/httpx before pytest.
- **Layer 2 — `features/*.md`** (frontmatter `id`/`name` + Markdown body):
  `login`, `tasks`, `reports`, `logging`, `user_identity` (base rule: user id is
  an email; invalid → 422).
- **Layer 3 — `customers/*.yaml`**:
  - `customer_one.yaml` — `extend` login (require a `captcha` field == "PASS",
    else 400) and `disable` reports (→ 404 for CustomerOne).
  - `customer_two.yaml` — `override` user_identity (8-char alphanumeric id, not
    email; invalid → 422) and `add` `task_tags` (tenant-only tags on tasks).

`compose(load_project(...))` deterministically produces one effective spec:

1. Title `Multi-Tenant To-Do — Multi-Tenant Application`.
2. **Tech Stack** bullets.
3. **Tenancy** section listing both tenants + isolation requirement.
4. **Global Features**: each feature body, followed by "Per-tenant variations"
   (e.g. login shows CustomerOne's `_extend_` CAPTCHA rule; reports shows
   CustomerOne's `_disable_`; user_identity shows CustomerTwo's `_override_`).
5. **Tenant-specific features**: `task_tags` for CustomerTwo (from `add`).
6. **Cross-cutting requirements** (tests per variation, per-tenant seeding,
   deploy artifact + DEPLOY.md, and a README.md).

`_validate` guarantees every non-`add` override points at a real feature id
(otherwise a hard error). The result is wrapped by `SpecDocument.from_text` and
handed to the **exact same** `Orchestrator`, so tenant overrides become
conformance-checkable requirements for free.

### (g) Config resolution precedence & `.env`

Two layers of environment resolution:

1. **`.env` loading** (`cli._load_dotenv`, run in the `main` group callback):
   fills environment variables that are **unset**, so a real shell export always
   wins over `.env`. `.env` is gitignored.
2. **Config resolution** (`AppConfig.resolve`): applies env vars, then
   `.agentloop.toml`, then CLI flag overrides (with `None` flags dropped). Net
   precedence:

   **CLI flags > `.agentloop.toml` (cwd) > env vars (`AGENTLOOP_*`) > defaults.**

Example (from `test_config`): a `.agentloop.toml` with `model="from-file"` +
`effort="high"`, env `AGENTLOOP_MODEL=from-env` + `AGENTLOOP_EFFORT=low`, and a
`--model from-flag` (but `--effort` unset) resolves to `model="from-flag"` (flag
wins) and `effort="high"` (file beats env; the `None` flag was dropped).

### (h) Building from a BRD (business-level input)

`agentloop build specs/leadgen-brd/brd.md` feeds a **business-level** document
(purpose, goals, actors, functional/non-functional requirements, constraints,
acceptance criteria — **no** schema or endpoints) into the same pipeline. Because
the CLI derives the project name from the folder for a bare `brd.md`, output goes
to `workspace/leadgen-brd/`. The **architect** reads the BRD and derives the schema,
endpoints, UI, layout, and requirement traceability into `design.md`; the
**design critic** must approve it (writing `design_review.json`) before the coder
runs. The template lives at `specs/_brd-template/brd.md`.

---

## 6. Engine layer contract & adapters

### The `Engine` protocol

One async method, `run_agent(*, system_prompt, task, workspace, tools, model,
effort) -> AgentResult`, plus a `name` attribute. The contract: the
implementation owns the entire tool-use loop and all LLM I/O, and **must confine**
file/command access to `workspace`. Everything above the seam depends only on
this protocol.

### The registry

`engines/registry.py` maps a config name to a **lazy factory**, so importing the
package never pulls in every backend's optional dependency. `get_engine(name)`
constructs on demand (and raises a helpful `ValueError` for unknown names). Four
factories are registered at import: `claude_api`, `agent_sdk`, `local`, `azure`.

### Adapters at a glance

| Engine | Backend | Loop owner | Tools exposed | Optional dep | `effort` used? |
|---|---|---|---|---|---|
| `claude_api` (default) | `anthropic.AsyncAnthropic` | this adapter (manual) | `bash`, `str_replace_based_edit_tool` (schema-less) | `anthropic` (core) | yes (+ adaptive thinking) |
| `agent_sdk` | `claude-agent-sdk` | the SDK | `Bash/Read/Write/Edit/Glob/Grep` | `claude-agent-sdk` | no (SDK-managed) |
| `local` | `openai.AsyncOpenAI` (Ollama/LM Studio/vLLM) | `_openai_common` | `run_bash/write_file/read_file/str_replace/list_files` | `openai` | no |
| `azure` | `openai.AsyncAzureOpenAI` | `_openai_common` | same as `local` | `openai` | no |

### Generic → per-backend tool-name mapping

The pipeline speaks in generic names (`DEFAULT_TOOLS`). Each adapter translates:

- `agent_sdk`: `_TOOL_NAME_MAP` (`bash`→`Bash`, `write`→`Write`, …).
- `local`/`azure`: the `_openai_common.TOOLS` function schemas (`write_file`,
  `run_bash`, …).
- `claude_api`: ignores the generic names and always wires the two
  Anthropic-defined tools.

### Azure specifics

- The **deployment name is the model**. If `--model` is a Claude default (starts
  with `claude`) or unset, the adapter uses `AZURE_OPENAI_DEPLOYMENT_NAME`; the
  CLI's `_effective_model` also pre-fills the model from that var so the
  report/transcript stay accurate.
- Required env vars (checked at construction with a clear error): endpoint, API
  key, API version, deployment name — typically supplied via `.env`.

---

## 7. CLI reference

Three commands under `agentloop`:

| Command | Argument | Purpose |
|---|---|---|
| `build` | `SPEC_PATH` (a `.md` file — a `spec.md` or `brd.md`) | Build from a single flat spec or BRD. |
| `build-project` | `PROJECT_DIR` (a layered dir) | Compose the three layers, then build. |
| `compose` | `PROJECT_DIR` | Render the effective spec (no LLM); print or write it. |

`build` and `build-project` share the `build_options` flags:

| Flag | Type / values | Default | Meaning |
|---|---|---|---|
| `--out`, `-o` | dir path | `workspace/<name>` | Output directory. Overrides the default `<workspace>/<name>` location entirely. |
| `--name` | str | derived from spec | Project folder name under the workspace root (slugged). |
| `--workspace` | dir path | `workspace` | Root directory that holds each project's output folder. |
| `--engine` | choice of registered engines | `claude_api` | LLM backend adapter. |
| `--model` | str | `claude-opus-4-8` | Model id (Azure: deployment). |
| `--effort` | str | `xhigh` | `output_config.effort` (claude_api only). |
| `--max-iterations` | int | `6` | Max test-fix iterations. |
| `--smoke-run/--no-smoke-run` | bool | on | Run the smoke stage (start/exercise the app) after tests. |
| `--max-smoke-iterations` | int | `2` | Max smoke-run→coder-fix cycles. |
| `--language` | str | spec hint, else `python` | Target language. |
| `--test-command` | str | inferred from language | Override the test runner. |
| `--design-review/--no-design-review` | bool | on | Run the architect+critic design gate before coding. |
| `--max-design-iterations` | int | `3` | Max design review→revise cycles. |
| `--conformance/--no-conformance` | bool | on | Run the conformance stage. |
| `--max-conformance-iterations` | int | `2` | Max review→fix cycles. |
| `--verbose` | flag | off | Write `<out>/build.log` transcript. |
| `--dry-run` | flag | off | Resolve config + print plan; no LLM calls. |
| `--debug` | flag | off | Re-raise (full traceback) on failure. |

`compose` takes only `--out/-o` (optional): with it, the composed spec is written
to that file; without it, the raw text is echoed to stdout (no rich markup, so it
pipes cleanly).

- **`--design-review`/`--no-design-review`** toggles the architect+critic gate.
  When on, the printed plan and final summary show the design verdict (yes/no +
  cycle count), and if the design is rejected the summary/report show a
  **gate-stop** line and no code is generated.
- **`--verbose`** produces a build transcript: a header, then per stage a block
  of tool calls (`[ok]`/`[ERR] name: summary`) and the agent's final message,
  plus each test run's exit code and the tail of its output, and the design and
  conformance verdict JSON.
- **`--dry-run`** stops after `_print_config` — useful to confirm the resolved
  engine/model/effort/test-command/design-review/smoke-run/output before spending
  tokens.

Exit codes: `0` success; `1` incomplete build or runtime error; `2` bad spec /
layered-spec input.

---

## 8. Security model

The `Workspace` is the sole security boundary. **All** file I/O and command
execution flow through it, and everything is confined to the `--out` directory.

- **Path-traversal guards on every file op.** `Workspace.resolve` resolves each
  path against the root and raises `WorkspaceError` unless the resolved path *is*
  the root or has the root among its `.parents`. Because it calls `.resolve()`
  first (which follows symlinks), this rejects `..` traversal, absolute paths
  outside root, *and* symlink escapes. Every `write_file`/`read_file`/`exists`/
  `append_file` routes through it. Tests assert `../escape.txt` and `/etc/passwd`
  are rejected.
- **Scoped, timed `run_command`.** Commands run with `cwd` pinned to the root and
  a default 300s timeout; a timeout yields `exit_code=124`, `timed_out=True`.
  Every backend's `bash`/`run_bash` tool and the orchestrator's test runs go
  through this one method.
- **Generated code IS executed.** Running the tests executes the model-authored
  code (and any `bash` tool call the model makes). The sandbox contains file and
  command access to the output dir, but the code itself is still untrusted — the
  README and `workspace.py` both warn: **run builds in a container or throwaway
  VM.** There is no CPU/memory/network isolation beyond the timeout.
- **Tool errors are surfaced, not hidden.** Engine dispatchers catch
  `WorkspaceError` and other exceptions and return them to the model as `error:
  …` strings (with `is_error`/`ok=False`), so the model can self-correct rather
  than the process crashing.
- **Secrets / `.env` handling.** `.env` is gitignored and loaded by the CLI only
  to fill *unset* env vars (shell exports win). API keys
  (`ANTHROPIC_API_KEY`, `AZURE_OPENAI_API_KEY`, `AGENTLOOP_API_KEY`) live in the
  environment; the `logging` example feature and prompts explicitly say never to
  log passwords/hashes/tokens, but note the framework does not scrub secrets from
  generated output on your behalf.

---

## 9. Testing

The suite is fully **offline**: no test touches the network or a real LLM. The
key enabler is a `FakeEngine` implementing the `Engine` protocol.

- **`conftest.py` — `FakeEngine` + `fake_engine_registered` fixture.**
  `FakeEngine.run_agent` inspects the incoming `system_prompt` to decide which
  role it's playing and writes **real files** into the workspace, simulating each
  agent. The dispatch order matters — the **design-critic** and **revise**
  branches are checked *before* the architect branch (their prompts also contain
  design keywords):
  - design critic (`"DESIGN CRITIC"`) → `design_review.json`. Two scripting
    knobs drive it: `design_reject_first` (reject until a revise has happened)
    and `design_never_approve` (always reject — the hard-gate test). A rejection
    verdict carries a high-severity issue; otherwise `{"approved": true,
    "issues": []}`.
  - architect revise (`"revising your design"`) → rewrites `design.md` and sets
    `_design_revised = True`.
  - architect (`"ARCHITECT"`) → `design.md`.
  - The **coder-fix** branch (`"fix iteration"`) is checked *before* the
    initial-coder branch, because `CODER_FIX` contains both `"CODER"` and `"fix
    iteration"`; the fix turn rewrites `app.py` to `VALUE = 2`.
  - coder (`"CODER"`) → `app.py` with a **wrong** `VALUE = 111`; tester
    (`"TESTER"`) → `check.py` asserting `app.VALUE == 2`; deployer → `deploy.sh`.
    This scripts a **fail-once-then-pass** sequence so the test-fix loop is
    exercised end-to-end. (A comment notes the wrong value has a different length
    so Python's `.pyc` cache is invalidated between runs.)
  - smoke (`"SMOKE TESTER"`, checked before the generic `"TESTER"` branch) →
    writes `smoke_check.sh` that `exit 0` by default, or `exit 1` when the
    `smoke_fail` knob is set — driving the smoke-passes and smoke-failure tests.
  - conformance: first review writes a non-conformant verdict with a
    high-severity issue; after a fix turn (`_conf_fixed = True`) the re-review
    writes a conformant verdict — exercising review→fix→re-review.
  - The fixture registers the fake under `"fake"` and pops it afterward.

- **`test_design_loop.py`** — the design gate via `FakeEngine`:
  - reject-once → revise → re-review approve → coding proceeds (`design_iterations
    == 1`, calls begin `architect, design_review, design_revise, design_review`,
    `coder` runs);
  - **hard gate**: `design_never_approve` → the budget is exhausted, `coder`/
    `tester` never run, no `app.py`, `report.ok is False`,
    `stopped_at_design_gate is True`, and `report.md` says "stopped at the design
    gate";
  - default critic approves first time (`design_iterations == 0`, calls
    `architect, design_review, coder`);
  - `--no-design-review` → `design_approved is None`, no `design_review` call,
    but the architect still produces `design.md`.

- **`test_orchestrator.py`** — the end-to-end pipeline via `FakeEngine` (these
  tests set `design_review=False` **and `smoke_run=False`** to keep the exact
  call-order assertions focused on the coder/tester/deployer/conformance stages):
  - all roles run in order (`architect, coder, tester, fix, deployer`) and the
    loop converges (one fix iteration; final `app.py == "VALUE = 2"`, report
    contains `SUCCESS`);
  - `max_iterations` bounds a never-passing loop (`test_command="exit 1"`,
    reports incomplete);
  - the conformance loop reviews → fixes → re-reviews (`conformant is True`, 1
    cycle);
  - `--verbose` writes a `build.log` with stage headers (`## STAGE: architect`,
    `## STAGE: coder`), tool calls, and `[test run 0]`;
  - `--no-conformance` skips the stage (`conformant is None`).

- **`test_smoke.py`** — the smoke stage via `FakeEngine` (each config sets
  `conformance=False`, `design_review=False`):
  - **smoke passes by default**: `"smoke"` is in the call list, `smoke_check.sh`
    exists, `smoke_passed is True`, `smoke_iterations == 0`, `report.ok is True`;
  - **`smoke_run=False`** skips the stage (no `"smoke"` call, `smoke_passed is
    None`);
  - **smoke failure feeds the coder and gates `ok`**: with `smoke_fail=True` and
    `max_smoke_iterations=1`, the coder is asked to fix (`"fix"` in the calls),
    `smoke_passed is False`, `smoke_iterations == 1`, and `report.ok is False`.

- **`test_config.py`** — defaults; the flag > file > env precedence; env used when
  no file/flag; language → test-command inference.
- **`test_layered_spec.py`** — loads all three layers; compose includes tenancy +
  every directive kind (`extend`/`override`/`disable`/`add`); determinism;
  unknown-feature and invalid-directive hard errors; single-tenant projects have
  no tenancy section; missing `stack.yaml` errors.
- **`test_registry.py`** — the four built-in engines are registered; unknown
  engine raises; the fake engine is selectable.
- **`test_spec.py`** — title from H1 and fallback to stem; language hint;
  missing/empty file errors.
- **`test_workspace.py`** — write/read round-trip; path-traversal rejection;
  `run_command` scoped to root; non-zero exit; timeout.
- **`test_cli_env.py`** — `.env` sets unset keys, respects quotes, and never
  overrides an already-set var; a missing `.env` is a no-op.

`pyproject.toml` sets `asyncio_mode = "auto"` (async tests run without explicit
markers) and `testpaths = ["tests"]`.

---

## 10. Extension points

### Add a new engine

1. Create `engines/<name>.py` with a class exposing `name` and implementing
   `async run_agent(*, system_prompt, task, workspace, tools, model, effort) ->
   AgentResult`. Confine all file/command access to a `Workspace(workspace)`. If
   your backend speaks OpenAI function calling, just build the client and call
   `run_openai_tool_loop` (like `local`/`azure`); otherwise write the loop
   yourself (like `claude_api`). Guard the optional import in `__init__` with a
   clear `RuntimeError`.
2. Add a lazy `_make_<name>` factory in `registry.py` and `register("<name>",
   _make_<name>)`. It now appears in `--engine`'s choices and
   `available_engines()`.
3. (Optional) declare an extras group in `pyproject.toml` for its dependency.

Nothing in the orchestrator or agents changes — that's the point of the seam.

### Add a new agent / gate (data only — no Python)

Agents and extra gates are data now, so this needs **no code**. Point at an
`agent_defs_dir` (`--agent-defs-dir` / `AGENTLOOP_AGENT_DEFS_DIR`) containing:
1. `prompts/<name>.md` for each new prompt (use `${var}` for interpolation).
2. `agents.yaml` with `agents:` entries (`{role?, prompt, task, tools?}`) that
   add/override by action id, and — for a generate→critique→gate stage — a
   `gates:` entry naming `generator`/`critic`/`verdict_file`/`placement`
   (`pre_<stage>`/`post_<stage>`) and `blocking`. The orchestrator runs it via the
   shared `_critique_gate` at that placement; a `blocking` `pre_code` gate stops
   the build like the design gate.
3. Optionally `[agentloop.agents.<role>]` in `.agentloop.toml` to route it to a
   model. See §4.3 for the full worked Security example.

Only a genuinely new *kind* of stage (not a generate→critique→gate) needs a new
Python `_stage_*`/loop and an entry in `Orchestrator._STAGE_NAMES`.

### Add a new layered-spec directive

1. Add the name to `DIRECTIVES` in `layered_spec.py` (so `_load_customers`
   accepts it).
2. Handle it in `compose`: decide whether it groups under an existing feature
   (like `extend`/`override`/`disable`) or stands alone (like `add`), and render
   its rules into the effective spec. If it targets an existing feature, make
   sure `_validate` still requires a known feature id for it.
3. Add coverage in `test_layered_spec.py` for the new rendering and any new error
   condition.

Because the effective spec is plain Markdown consumed by the same pipeline, a new
directive automatically becomes a design/conformance-checkable requirement.
