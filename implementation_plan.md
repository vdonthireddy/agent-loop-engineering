# Implementation Plan: Multi-File Dynamic Workspace

## The Misunderstanding
Currently, our engine assumes that an agent only ever generates a single string of code, which we then hardcode into `deployed_app.py`. 

As you pointed out, a real agentic framework needs to handle multiple specs resulting in multiple, dynamically named files. The LLM must be in control of file creation and architecture, not our Python orchestrator.

## Proposed Architecture

### 1. Multi-File Output Protocol
We will update `config/agents.yaml` to instruct the agents to output multiple files using a standardized markdown format.
**Example Prompt Instruction:**
> Output your code in the following format:
> # File: `filename.py`
> ```python
> code here
> ```

### 2. The File System as the State Machine
We will completely replace the in-memory `GlobalState` dictionary with a File-System backed `Workspace` manager in `engine.py`.

#### Writing (Outputs):
When a phase (e.g., `tester`) declares `output_key: "test"`, the engine will:
1. Parse the LLM's response using Regex to extract the dynamic filenames and code blocks.
2. Physically write those files to `workspace/test/<filename>`.

#### Reading (Inputs):
When the next phase (e.g., `coder`) declares `inputs: ["specs", "test"]`, the engine will:
1. Scan the physical `workspace/test/` directory.
2. Concatenate all the files inside it into a structured prompt context (e.g., "File: `test_auth.py` \n <content> ...").
3. Inject that bundle into the Actor's prompt.

### 3. Benefits to Loop Engineering
- **True Autonomy:** The LLM decides how many files to create, what to name them, and how to structure the project.
- **Auditability:** You can open your IDE during execution and watch the folders populate with real files as the agents iterate through loops.
- **No Hardcoding:** `main.py` is entirely decoupled from file naming logic.

## User Review Required
> [!IMPORTANT]
> This represents a massive leap toward a production-grade agent framework. The engine will literally parse and inject entire directories on the fly.
> 
> Does this file-system backed, multi-file generation approach capture your vision? If so, hit Proceed!
