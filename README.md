# Agent Loop Engineering

A generic, purely data-driven agentic framework built using standard Python and the official `ollama` SDK. 

This project explores a **Universal Actor-Critic Architecture** designed to take arbitrary specifications and turn them into robust, test-driven code.

## Architecture Highlights

- **Zero LangChain/Heavy Frameworks**: Built natively with the `ollama` Python package to keep things blazing fast and completely transparent.
- **Data-Driven Engine**: All LLM prompts, context injection rules, and parsing logic have been externalized to `config/agents.yaml`.
- **Universal Actor-Critic**: Every artifact produced by the pipeline undergoes rigorous peer-review. 
  - An **Actor** generates the output.
  - A **Critic** reviews it.
  - If the Critic finds flaws, it feeds the critique directly back into the Actor for a rewrite, automatically looping up to 3 times before either passing or safely aborting.

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
