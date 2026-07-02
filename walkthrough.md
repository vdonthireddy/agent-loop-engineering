# Loop Engineering Framework

I have successfully upgraded the multi-agent system into a completely generic **Loop Engineering Playground**. You can now orchestrate entire LLM workflows and state machines without writing a single line of Python.

## Architecture & Structure

The codebase is now incredibly lean, consisting of just three core files:

```
agent-loop-engineering/
├── main.py            (The Universal Orchestrator CLI)
├── engine.py          (The DAG Execution Engine)
├── utils/
│   └── llm.py         (Shared Ollama connection logic)
└── config/
    └── agents.yaml    (The control plane)
```

## How It Works

### 1. Multi-File Dynamic Workspace
Instead of holding Python strings in memory, the engine uses the File System as its state machine. 
- Agents are prompted to output files using a standardized markdown format (e.g., `# File: app.py`).
- The engine dynamically creates these files in the `workspace/` root.
- When an agent needs inputs, the engine bundles entire directories from the `workspace/` folder and injects them into the prompt. The LLM dictates the file architecture, not the python orchestrator.

### 2. Directed Acyclic Graphs (DAGs)
You define the exact sequence of events in `config/agents.yaml` under the `workflow` block. 
```yaml
workflow:
  name: "TDD_Pipeline"
  steps:
    - phase: "tester"
      inputs: ["specs"]
      output_key: "tests"
```
You can reorder phases, add new phases, or completely alter the data flow just by editing the YAML.

### 3. Pluggable Loop Strategies
Actor-Critic is no longer hardcoded. The framework uses a `LoopFactory`. Every phase in your YAML can specify its own `loop_strategy`:
- `linear`: A simple one-shot LLM call.
- `actor_critic`: The generation and review loop we built earlier.
- `tdd`: **Test-Driven Development.** The engine saves the code to disk, executes a deterministic evaluator (like `pytest`), and feeds the `stderr` traceback back to the LLM until the tests pass!

## Execution Results

I ran `python main.py` using `qwen2.5-coder:7b` with the new **TDD Execution Loop**.

**The TDD Loop Works Flawlessly:** 
1. The **Tester Agent** generated `test_math_utils.py` using `pytest`.
2. The **Coder Agent** generated `math_utils.py` and the engine saved it to disk.
3. The **TDD Evaluator** spawned a subprocess and ran `pytest workspace/tests`.
4. The tests turned green on the very first attempt! `============================== 2 passed in 0.02s ===============================`

> [!NOTE]
> The Deployer phase was aborted because the 7B LLM critic was overly pedantic (suggesting Kubernetes configs for a simple math script), but the TDD code generation loop was successfully proven!
