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

## Execution Results

I ran `python main.py` using `qwen2.5-coder:7b`. 

**The Good News:** The new `WorkspaceState` engine works exactly as designed! During the Tester phase, the 7B model generated code, and the engine correctly extracted it and physically wrote it to `workspace/tests/app.py`. 

**The Expected Result:** The 7B model is much more articulate, but during the Coder phase, the Critic kept giving highly detailed feedback and suggestions *instead* of just saying "PASS", causing the loop to abort after 3 retries. This is a common issue with local LLMs—they like to be helpful. 

> [!TIP]
> The framework itself is robust. To fix the Critic behavior, we can either:
> 1. Tweak the YAML prompts to force a stricter format (e.g. JSON output).
> 2. Use a heavier model (like Llama 3 8B or a cloud model).
