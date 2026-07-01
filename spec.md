# To-Do App — Product Specification

## Overview
A minimal but functional to-do list web application built with Flask and SQLite.

## Core Features

### 1. Task Management (CRUD)
- **Add a task:** User enters a title via a form and submits it.
- **List tasks:** All tasks are displayed on the main page, showing title and status.
- **Complete a task:** User can mark a task as done (toggle).
- **Delete a task:** User can remove a task permanently.

### 2. Data Storage
- Use Python's built-in `sqlite3` module (no ORM).
- Database file: `todo.db` in the app's working directory.
- Schema: `tasks` table with columns `id` (INTEGER PRIMARY KEY), `title` (TEXT NOT NULL), `done` (BOOLEAN DEFAULT 0).

### 3. Web Interface
- Single-page UI rendered with Jinja2 templates.
- HTML form at the top for adding new tasks.
- Task list below with checkboxes for completion and delete buttons.
- Minimal inline CSS for readability (no external frameworks required).

### 4. Routes
| Route | Method | Action |
|---|---|---|
| `/` | GET | Show all tasks |
| `/add` | POST | Add a new task |
| `/complete/<id>` | POST | Toggle task completion |
| `/delete/<id>` | POST | Delete a task |

### 5. Testing
- Write pytest tests in `tests/test_app.py`.
- Tests should use Flask's test client (no real server needed).
- Cover: adding a task, listing tasks, completing a task, deleting a task.
- Use a temporary database for each test (not the production `todo.db`).

## Constraints
- Python 3.10+
- Flask (latest stable)
- No external CSS/JS frameworks
- All code in a single `app.py` plus `templates/` and `tests/`
