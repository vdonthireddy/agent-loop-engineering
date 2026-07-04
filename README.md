# Agent Loop Engineering

A generic, purely data-driven agentic framework built using standard Python. 

This project is a laboratory for **Loop Engineering**—the science of designing, orchestrating, and optimizing generic agentic feedback loops. The goal is to create a pure data-driven framework where complex LLM workflows (loops) can be engineered to solve any problem.

## Loop Engineering Focus

- **Data-Driven Loops**: All LLM prompts, context injection rules, and loop orchestration are externalized to `src/agent_loop_engineering/agents.yaml`. This allows us to engineer new loop topologies purely through configuration.
- **Current Implementation (Actor-Critic)**: As a proof-of-concept for loop engineering, the current default configuration utilizes an Actor-Critic architecture where artifacts are generated and peer-reviewed in a feedback loop. However, the framework itself is entirely loop-agnostic.
- **Multiple Engines Supported**: Supports local execution (via Ollama or similar local servers) as well as Anthropic and OpenAI models.

## The Pipeline Flow

The framework currently defaults to the following pipeline defined in `agents.yaml`:
1. **Phase 1 (Design)**: An Architect agent derives a technical design from the spec. A Design Critic reviews it.
2. **Phase 2 (Implementation & Test)**: A Coder agent writes the implementation, and a Tester agent writes the test suite. If tests fail, the Coder iteratively fixes the code.
3. **Phase 3 (Smoke Test)**: Generates and runs a smoke test script to prove the application starts.
4. **Phase 4 (Deployment)**: A Deployer agent produces deployment artifacts (e.g., Dockerfile).
5. **Phase 5 (Conformance)**: A Conformance review ensures the final implementation meets the original specification requirements.

## Getting Started

### Prerequisites
- Python 3.10+
- Local LLM running (like Ollama) OR API keys for Anthropic/OpenAI

### Installation
```bash
git clone <your-repo-url>
cd agent-loop-engineering
pip install -e .
```

### Usage
1. Place your markdown specification documents into a `specs/` directory.
2. Set your environment variables (e.g. in a `.env` file) or configure via CLI options.
3. Run the orchestrator using the CLI:
```bash
agentloop build specs/your_spec.md --engine <engine_name> --model <model_name>
```
*(Use `agentloop build --help` for all available options, including `--out`, `--test-command`, etc.)*

## Customizing Agents

You do not need to write any Python code to create new agents! 
Simply edit `src/agent_loop_engineering/agents.yaml` to define your own phases, actors, and critics. The underlying orchestrator will dynamically parse your YAML and execute the LLM loops automatically.
