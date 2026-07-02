# Frontend UI Specification

The frontend must provide a clean, interactive user interface for managing tasks.

**Requirements:**
1. **Technology**: Use plain HTML/CSS and Vanilla JavaScript. (Do not use heavy frameworks like React so the backend can serve the static files easily).
2. **Login/Register Page (`index.html`)**:
   - A form with fields for `Username` and `Password`.
   - Two buttons: "Login" and "Register".
   - When submitted, the JavaScript should make an AJAX/fetch call to the backend API (`/login` or `/register`).
   - On successful login, redirect the user to the Task Dashboard.
3. **Task Dashboard Page (`dashboard.html`)**:
   - A header showing "Welcome, [username]".
   - A form at the top to add a new task (Inputs: `Title`, `Description`, Button: `Add Task`).
   - A dynamic list/grid displaying all existing tasks fetched from the `GET /tasks` API.
   - Each task item in the list must have:
     - A checkbox or button to "Mark as Done" (calls `PUT /tasks/{task_id}`).
     - A "Delete" button (calls `DELETE /tasks/{task_id}`).
4. **Integration**:
   - Ensure the backend web server is configured to serve these HTML/JS/CSS files statically.
