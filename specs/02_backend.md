# Backend API Specification

The backend serves as the bridge between the UI and the Database. It handles authentication and task management.

**Requirements:**
1. **Technology**: Use `FastAPI` or `Flask` for the web server.
2. **Authentication Routes**:
   - `POST /register`: Accepts `username` and `password`. Hashes the password and stores it in the database. Returns a success message.
   - `POST /login`: Accepts `username` and `password`. Verifies credentials and returns a session token or sets a secure cookie to identify the logged-in user.
3. **Task Routes (Must be authenticated)**:
   - `GET /tasks`: Returns a list of all tasks belonging to the logged-in user.
   - `POST /tasks`: Accepts `title` and `description`. Creates a new task for the logged-in user.
   - `PUT /tasks/{task_id}`: Accepts a boolean `is_completed` or updated `title`/`description`. Updates the task in the database.
   - `DELETE /tasks/{task_id}`: Deletes the specified task, ensuring it belongs to the logged-in user.
4. **File Output**:
   - Create `backend.py` to hold these routes and integrate with the database layer defined in `db.py`.
