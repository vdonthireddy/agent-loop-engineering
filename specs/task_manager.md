# Task Manager System

We need a modular task management backend in Python. The application MUST be split into exactly three files:

1. `models.py`
- Create a `Task` dataclass with fields: `id` (int), `title` (str), `description` (str), and `completed` (bool).

2. `storage.py`
- Import `Task` from `models`.
- Create an `InMemoryStorage` class that stores tasks in a dictionary mapping `id` to `Task`.
- Must have methods: 
  - `save(task: Task)`: Saves the task.
  - `get(task_id: int) -> Task`: Returns the task or None.
  - `get_all() -> list[Task]`: Returns all tasks.
  - `delete(task_id: int)`: Deletes the task.

3. `manager.py`
- Import `Task` from `models` and `InMemoryStorage` from `storage`.
- Create a `TaskManager` class initialized with a `storage` instance (defaults to a new `InMemoryStorage`).
- Must have methods: 
  - `add_task(title, description) -> Task`: Auto-increments ID (starting at 1), creates a Task (completed=False), saves it, and returns it.
  - `complete_task(task_id: int)`: Marks the task as completed=True and saves it.
  - `list_pending_tasks() -> list[Task]`: Returns only tasks where completed=False.
