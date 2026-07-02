# Loop Engineering Framework: Architectural Design

To stay true to our core philosophy—that this is a laboratory for **Loop Engineering**—we need to address a major flaw in our current setup.

While we successfully externalized the prompts into `agents.yaml`, our orchestrator (`main.py`) still hardcodes the workflow (`Tester` -> `Coder` -> `Deployer`) and hardcodes the context passing (`context = {'specs': specs, 'tests': tests}`). 

This defeats the purpose of loop engineering, as creating a new workflow currently requires rewriting Python. To fix this, I propose upgrading our engine to a completely dynamic, state-driven architecture.

## Proposed Architecture

### 1. Global State Management
Instead of passing variables manually between functions, the engine will maintain a `Global State` (a shared key-value dictionary) throughout the execution. 
- Phases will declare which keys they `read` from the state.
- Phases will declare which keys they `write` back to the state upon completion.

### 2. YAML-Defined Topologies (DAGs)
We will add a `workflow` block to `config/agents.yaml`. This allows us to define the exact sequence of events, and map the inputs/outputs for each phase without writing a single line of Python.

**Example:**
```yaml
workflow:
  name: "TDD_Pipeline"
  steps:
    - phase: "tester"
      inputs: ["specs"]        # Reads 'specs' from Global State
      output_key: "tests"      # Saves output to Global State as 'tests'
    - phase: "coder"
      inputs: ["specs", "tests"]
      output_key: "code"
    - phase: "deployer"
      inputs: ["code", "tests"]
      output_key: "manifest"
```

### 3. Pluggable Loop Types
To truly prove that "Actor-Critic is just one implementation," we will refactor `engine.py` to support pluggable loop strategies. 
Each phase in the YAML will specify its `loop_strategy`.

**Example Loop Strategies:**
1. `linear`: A simple, single-shot LLM call (No critic).
2. `actor_critic`: The loop we just built (Actor generates, Critic reviews and loops up to N retries).
3. `consensus` (Future Idea): 3 parallel Actors generate solutions, a Critic evaluates and picks the best one.

### 4. The Universal Orchestrator (`main.py`)
`main.py` will become completely agnostic. Its only job will be to:
1. Load the initial `specs` into the Global State.
2. Read the `workflow.steps` from the YAML.
3. Dynamically instantiate the requested `loop_strategy` for each step.
4. Pass the required `inputs` from the State to the loop, and save the result back to the `output_key` in the State.

## User Review Required
> [!IMPORTANT]
> This design turns the framework into a true "Loop Engineering Playground". You will be able to swap out Loop Strategies (Linear vs Actor-Critic), re-order phases, and route data seamlessly just by editing the YAML file. 
> 
> Does this architecture align with your vision for the framework? If approved, I will begin implementing this DAG-based orchestration engine immediately.
