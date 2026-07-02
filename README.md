# Agent Loop Engineering

A generic, purely data-driven agentic framework built using standard Python and the official `ollama` SDK. 

This project is a laboratory for **Loop Engineering**—the science of designing, orchestrating, and optimizing generic agentic feedback loops. The goal is to create a pure data-driven framework where complex LLM workflows (loops) can be engineered to solve any problem.

## Loop Engineering Focus

- **Zero LangChain/Heavy Frameworks**: Built natively with the `ollama` Python package to keep things blazing fast and completely transparent, allowing us to focus entirely on the loop logic.
- **Data-Driven Loops**: All LLM prompts, context injection rules, and loop orchestration are externalized to `config/agents.yaml`. This allows us to engineer new loop topologies purely through configuration.
- **Current Implementation (Actor-Critic)**: As a proof-of-concept for loop engineering, the current default configuration utilizes an Actor-Critic architecture where artifacts are generated and peer-reviewed in a feedback loop. However, the framework itself is entirely loop-agnostic.

## The Pipeline Flow

The framework currently defaults to the following Test-Driven Development (TDD) pipeline:
1. **Phase 1 (Test Generation)**: A QA Agent reads the specs and writes `pytest` coverage. A QA Critic reviews the tests.
2. **Phase 2 (Code Generation)**: A Coder Agent reads the specs AND the generated tests to write the implementation. A Code Critic reviews it.
3. **Phase 3 (Deployment)**: A Deployer Agent takes the approved codebase and generates a deployment manifest. A DevOps Critic ensures it is safe and complete.

## Getting Started

### Prerequisites
- Python 3.10+
- [Ollama](https://ollama.com/) running locally with your desired models installed.

### Installation
```bash
git clone <your-repo-url>
cd agent-loop-engineering
pip install -r requirements.txt
```

### Usage
1. Place your markdown specification documents into the `specs/` directory.
2. Edit `utils/llm.py` to point to the local Ollama model you wish to use (e.g., `llama3` or `qwen2.5-coder:7b`).
3. Run the orchestrator:
```bash
python main.py
```

## Customizing Agents

You do not need to write any Python code to create new agents! 
Simply edit `config/agents.yaml` to define your own phases, actors, and critics. The underlying `engine.py` will dynamically parse your YAML and execute the LLM loops automatically.
