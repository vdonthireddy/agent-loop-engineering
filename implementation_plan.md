# Implementation Plan: Test-Driven Development (TDD) Loop

## Goal
Introduce a true Test-Driven Development (TDD) loop strategy where the generated code is actually executed against the unit tests using `pytest`. If the tests fail, the error trace is fed back to the LLM to update the code, looping up to a specified maximum (e.g., 10 times).

## Background
Currently, our `actor_critic` strategy uses another LLM (the Critic) to statically review the code. While useful, it is prone to hallucination or being overly pedantic (as we saw when it refused to just output "PASS"). A true TDD loop runs actual deterministic tests to evaluate success.

## Proposed Changes

### 1. `TDDStrategy` in `engine.py`
I will add a new `TDDStrategy` class to the `LoopFactory`.
- It will execute the Actor LLM to generate the implementation code.
- It will write the code to the workspace immediately so it can be tested.
- It will spawn a subprocess to run `python3 -m pytest workspace/tests` (or similar).
- If the exit code is `0` (Success), the loop breaks and the phase is complete!
- If the exit code is non-zero (Failure), it will capture the `stderr`/`stdout` trace and inject it as `feedback` back into the Actor LLM for the next attempt.

### 2. Strategy Signature Update
To allow the `TDDStrategy` to evaluate files on disk, I will update the `LoopStrategy.execute()` signature to pass the `WorkspaceState` and the `output_key` so the strategy can save files mid-loop before evaluating them.

### 3. Update `agents.yaml`
- The `coder` phase will be updated to use `loop_strategy: "tdd"`.
- The `critic` block will be removed from the `coder` phase, as `pytest` is now the critic.
- A `max_retries` hyperparameter will be added to the `coder` phase (set to 10).
- The `feedback_prompt_template` will be updated to instruct the LLM on how to read python traceback errors.

## Verification
We will run `python main.py` again. We should see the engine physically running tests, capturing failures, and the LLM iteratively fixing its code until the tests pass green.

## User Review Required
> [!IMPORTANT]
> The `TDDStrategy` requires executing code on your local machine using a subprocess. Are you comfortable with the framework running `pytest` locally on the LLM-generated code?
> 
> If you approve of this TDD loop design, hit Proceed!
