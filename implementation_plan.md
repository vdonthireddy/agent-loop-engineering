# Refactoring Plan: Data-Driven Agent Engine

You are absolutely right. The current structure violates the DRY (Don't Repeat Yourself) principle. All actors and critics perform the exact same underlying mechanics: format a prompt, call the LLM, and parse the output.

To make this framework truly generic, we will transition to a **Data-Driven Architecture** where the agents are defined purely by configuration files, rather than hardcoded Python scripts.

## Proposed Changes

### 1. Externalize Prompts into YAML
**[NEW] [config/agents.yaml](file:///Users/donthireddy/code/ollama-linkedin/agent-loop-engineering/config/agents.yaml)**
We will create a YAML file that defines the system prompts, user prompt templates, and output behaviors (e.g., whether to extract a python code block) for every Actor and Critic. 

*Example structure:*
```yaml
tester:
  actor:
    system_prompt: "You are an expert QA Tester Agent..."
    extract_code: true
  critic:
    system_prompt: "You are a Senior QA Critic Agent..."
```

### 2. Create a Generic Agent Engine
**[NEW] [engine.py](file:///Users/donthireddy/code/ollama-linkedin/agent-loop-engineering/engine.py)**
We will build a single, generic `run_actor()` and `run_critic()` function that dynamically loads its behavior from the YAML configuration. It will automatically inject the `specs`, `tests`, `code`, and `feedback` variables into the templates.

### 3. Simplify the Orchestrator
**[MODIFY] [main.py](file:///Users/donthireddy/code/ollama-linkedin/agent-loop-engineering/main.py)**
`main.py` will no longer import 6 different agent files. Instead, it will initialize the `engine` with `agents.yaml` and run the pipeline loops dynamically.

### 4. Delete the Boilerplate
**[DELETE] `agents/` Directory**
We will completely delete the `agents/coder`, `agents/tester`, and `agents/deployer` folders, drastically reducing the boilerplate and complexity of the project.

### 5. Add PyYAML Dependency
**[MODIFY] [requirements.txt](file:///Users/donthireddy/code/ollama-linkedin/agent-loop-engineering/requirements.txt)**
We will add `PyYAML` to the dependencies to parse the new configuration file.

## User Review Required
> [!IMPORTANT]
> This refactor will eliminate over a dozen Python files and condense the entire framework into a single YAML configuration and a tiny execution engine. 
> Does this YAML-driven approach align with your vision for making the framework "generic and maintainable"?
