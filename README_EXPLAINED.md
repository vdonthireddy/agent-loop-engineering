# Explaining the README: A Deep Dive into "3. Run"

This document breaks down the **"3. Run"** section of the `README.md` file in this project, explaining exactly what happens under the hood when you execute each command in the CLI.

---

### Command 1: `loop-eng init`
**What it means:** Initialize the project.
**What happens under the hood:**
- **Creates the Product Spec:** It writes a default `spec.md` file to the root of the project. This file is the "source of truth" containing the requirements for the Flask To-Do app.
- **Creates the Workspace:** It creates a `workspace/` folder. This is the sandbox where the AI will write the Python and HTML files.
- **Resets History:** It creates or clears a `loop_history.json` file, which tracks every iteration, pass/fail result, and LLM timing metrics.

---

### Command 2: `loop-eng code`
**What it means:** Run Loop 1 (Agentic Coding). This is the fastest, tightest loop (measured in minutes).
**What happens under the hood:**
1. The CLI reads the `spec.md` file.
2. It sends the spec to the local Ollama LLM with a strict prompt: "Write this code and output it in code blocks."
3. The LLM responds with code.
4. Our robust "Extractor" parses the LLM's response, grabbing `app.py`, `templates/index.html`, and `tests/test_app.py`, and writes them to the `workspace/`.
5. The system automatically runs `pytest` in the background.
6. **The Loop:** If tests fail, the system grabs the red error text, sends it *back* to the LLM, and says "Fix this." It repeats this up to 5 times until the tests pass.

---

### Command 3: `loop-eng dev`
**What it means:** Run Loop 1 + Loop 2 (Developer Feedback). This operates on the scale of hours.
**What happens under the hood:**
1. It automatically runs **Loop 1** (`loop-eng code`) so that there is a working app to review.
2. The CLI pauses and asks the human developer: *"Review the app and enter feedback."*
3. The developer tests the app and types plain English feedback (e.g., "Make the background blue" or "Add a priority dropdown").
4. The system sends the developer's feedback, along with the *current* `spec.md`, to the LLM.
5. The LLM rewrites the `spec.md` to incorporate the new requirements.
6. **The Loop:** The system then automatically triggers Loop 1 again with the *new* spec, forcing the AI to code the new features.

---

### Command 4: `loop-eng full`
**What it means:** Run all 3 Loops end-to-end (External Feedback). This operates on the scale of days or weeks.
**What happens under the hood:**
1. It runs **Loop 2** (which internally runs **Loop 1**). Now we have a polished app that the developer approved.
2. The CLI launches a background web server on port `5001`. This is the **Feedback Portal**.
3. The developer shares this URL with real-world testers or users.
4. Testers use the website to submit bug reports or feature requests, which are saved to `feedback.json`.
5. When the developer presses Enter in the CLI to end the testing phase, the system reads all the collected feedback from the JSON file.
6. The LLM summarizes the external feedback, translates it into technical requirements, and updates `spec.md`.
7. **The Loop:** The system triggers Loop 2 again, starting the whole cycle over to build what the users actually asked for.

---

### Command 5: `loop-eng status`
**What it means:** Check the health and progress of the system.
**What happens under the hood:**
- It prints how many lines are in the current `spec.md`.
- It counts how many files the AI has generated in `workspace/`.
- It reads `loop_history.json` and prints a summary table of how many iterations have been run.
- It pings the Ollama server API to verify it's running and that the configured model (e.g., `qwen2.5-coder:0.5b`) is downloaded and ready.
