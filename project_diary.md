# Agent Loop Engineering: Project Diary

This document serves as a chronological diary of our ideas, thought processes, and architectural decisions as we build the generic agent loop framework.

---

### Entry 1: The Initial Idea
**Date:** July 2, 2026, ~09:25 AM

**Thought Process:** 
I wanted to build a completely generic agent framework that reads specification documents from a `specs/` folder and writes the corresponding code. I explicitly wanted to avoid bulky frameworks like LangChain and use only the raw `ollama` Python SDK. The system needed three distinct agents:
1. **Coder**: Reads specs and writes code.
2. **Tester**: Tests the code.
3. **Deployer**: Deploys the code.

**Decision:** 
We built a simple, monolithic orchestrator in `main.py` that passed data sequentially: Coder ➡️ Tester ➡️ Deployer. We used `qwen2.5-coder:0.5b` as the local model.

---

### Entry 2: Modularity & CLI
**Date:** July 2, 2026, ~09:32 AM

**Thought Process:** 
The monolithic `main.py` was too rigid. I wanted the agents organized clearly into different folders, and I wanted a client that could invoke a specific agent on demand instead of always running the full pipeline.

**Decision:** 
We refactored the project. We moved the shared Ollama logic to `utils/llm.py` and gave each agent its own folder (`agents/coder/`, `agents/tester/`, `agents/deployer/`). We rewrote `main.py` to use `argparse` so we could run things like `python main.py --agent coder`.

---

### Entry 3: The TDD Dilemma
**Date:** July 2, 2026, ~10:30 AM

**Thought Process:** 
I was stuck deciding the order of operations: Should the Tester write test cases for a feature *first* (requiring 100% coverage perfection), or should the Coder write the code and test in a loop until it's correct?

**Decision:** 
We discussed the trade-offs of Pure TDD vs Auto-Regressive Execution Loops. We decided that if a Tester writes tests first, it requires incredibly strict specs to avoid hallucinating the API surface. This led to the realization that we needed a safeguard to verify the tests themselves before the Coder sees them.

---

### Entry 4: The Universal Actor-Critic Pipeline
**Date:** July 2, 2026, ~10:38 AM

**Thought Process:** 
To solve the problem of flawed tests, we conceptualized a "Critic Agent" whose sole job is to review the Tester's output. I then realized this was such a good idea that *all* agents (Coder, Tester, Deployer) should have their own dedicated Critic agents.

**Decision:** 
We completely overhauled the framework into a **Universal Actor-Critic Architecture**:
- Every domain folder now contains an `actor.py` and a `critic.py`.
- `main.py` was rewritten to use a generic `run_loop()` function. 
- Now, whenever an Actor generates an artifact, its Critic reviews it. If the Critic finds flaws, it feeds the critique back to the Actor for a rewrite (looping up to 3 times) before the pipeline is allowed to advance to the next phase.

### Entry 5: The Data-Driven Refactor
**Date:** July 2, 2026, ~10:51 AM

**Thought Process:** 
I realized that having six different Python files for the Actors and Critics was a massive violation of the DRY (Don't Repeat Yourself) principle. Every single agent was essentially doing the exact same thing: formatting a string, calling the LLM, and occasionally running a regex to extract code. The framework wasn't truly generic yet.

**Decision:** 
We completely deleted the `agents/` folder and pivoted to a **Data-Driven Architecture**. We externalized all system prompts, user templates, and variables into a single `config/agents.yaml` file. We then created a tiny `engine.py` script that can dynamically instantiate and run *any* agent purely by reading the YAML file. This condensed the framework from over a dozen files down to just three core files!

### Entry 6: Philosophical Alignment - Loop Engineering First
**Date:** July 2, 2026, ~11:03 AM

**Thought Process:** 
I lost sight of the forest for the trees. I started treating the "Actor-Critic" architecture as the final goal of the project, framing the entire `README.md` around it. The user correctly pulled me back and reminded me that the primary focus of this framework is **Loop Engineering**—the actual science and tooling around designing, managing, and orchestrating arbitrary agentic loops.

**Decision:** 
We rewrote the documentation to accurately reflect this philosophy. The framework is a loop engineering laboratory. The Actor-Critic pipeline we built is merely *one* proof-of-concept configuration of a loop, not the defining feature of the framework. Going forward, all architectural decisions must serve the meta-goal of making loop design easier and more robust.

### Entry 7: DAG-Based Orchestration Engine
**Date:** July 2, 2026, ~11:17 AM

**Thought Process:** 
I realized that our previous refactor didn't go far enough. We externalized our prompts to a YAML file, but the orchestration logic (the loop) was still hardcoded in Python! `main.py` explicitly called `tester`, then `coder`, then `deployer` and manually wired the variables together. If you wanted to test a different sequence of loops or build a new agentic architecture, you would still have to rewrite Python code.

**Decision:** 
We built a **DAG (Directed Acyclic Graph) Engine**. 
1. `config/agents.yaml` now has a `workflow` block that defines the exact execution sequence and maps the Inputs/Outputs.
2. We created a `GlobalState` dictionary. Phases declare what keys they read from the state and what keys they write back.
3. We introduced a `LoopFactory`. Now, every phase in the YAML can specify its `loop_strategy` (e.g., `linear`, `actor_critic`). This definitively proves that Actor-Critic is just one possible loop type in our laboratory, and we can seamlessly plug in new strategies.

Our framework is now a true, no-code *Loop Engineering Playground*.

### Entry 8: Multi-File Dynamic Workspace (File-Backed State)
**Date:** July 2, 2026, ~11:47 AM

**Thought Process:** 
We realized our orchestration engine had a severe limitation: it assumed an LLM only ever outputs a single string of code, and our Python orchestrator hardcoded that output into a single file (`deployed_app.py`). In a real agentic framework, an LLM might read 5 spec files and decide it needs to create 3 Python files and a database model. The LLM must control the file architecture.

**Decision:** 
We are moving from an "In-Memory Global State" to a **File-System Backed Workspace**. 
1. The prompts in `agents.yaml` are being updated to instruct agents to use a standard markdown protocol for multi-file generation (e.g., `# File: db.py \n ```...```).
2. The engine parses this output via Regex and dynamically writes the files to disk (e.g., `workspace/code/db.py`).
3. When the next agent requests `inputs: ["code"]`, the engine physically scans the `workspace/code/` directory, bundles all the files it finds into a structured context window, and injects it. 

This makes the framework infinitely more powerful and completely decoupled from hardcoded file names.

### Entry 9: Test-Driven Development (TDD) Loop Strategy
**Date:** July 2, 2026, ~12:07 PM

**Thought Process:** 
Using an LLM as a "Critic" to review code is useful for qualitative review (like docs or manifests), but for code, it's often overly pedantic or prone to hallucination (e.g., refusing to output 'PASS' despite perfect code). A true loop engineering framework should be able to execute code against a deterministic evaluator.

**Decision:** 
We built a `TDDStrategy` to plug into the `LoopFactory`. 
Instead of an LLM Critic, the engine saves the Actor's generated code to the workspace and executes `pytest`. If the tests fail, the engine captures the stderr/stdout traceback and feeds it back into the Actor's prompt, creating a self-correcting TDD loop. We set the hyperparameter `max_retries` to 10. 
This elevates the framework from a simple LLM wrapper into an autonomous, test-driven coding agent.

### Entry 10: TDD Loop Execution and Validation
**Date:** July 2, 2026, ~12:27 PM

**Thought Process:**
After building the `TDDStrategy`, we needed to prove it worked in practice, handling an iterative code generation loop. Our first attempt failed because the LLM hallucinated markdown guides instead of tests when given too large of a prompt (`SPEC_FRAMEWORK.md`).

**Decision:**
We narrowed the scope to a simple `math.md` specification and made the Tester prompt strictly require the `test_*.py` filename prefix so Pytest could discover it. 
We then tested the true flexibility of the loop by injecting a new feature (`subtract`) into the spec mid-development. The TDD execution loop kicked in: the Tester updated the test suite, the Coder implemented the new feature, and the engine executed `pytest` in a background subprocess, passing flawlessly on the first attempt (`3 passed`).
The TDD execution loop is now fully autonomous and driven by real deterministic evaluation!

*(To be continued...)*
