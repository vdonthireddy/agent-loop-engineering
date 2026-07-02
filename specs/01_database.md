# Database Specification

The application requires a robust database layer to store users and tasks persistently.

**Requirements:**
1. **Technology**: Use `sqlite3` for a lightweight, file-based database.
2. **Schema Definition**:
   - `users` table: 
     - `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
     - `username` (TEXT UNIQUE NOT NULL)
     - `password_hash` (TEXT NOT NULL)
   - `tasks` table:
     - `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
     - `user_id` (INTEGER FOREIGN KEY referencing `users(id)`)
     - `title` (TEXT NOT NULL)
     - `description` (TEXT)
     - `is_completed` (BOOLEAN DEFAULT 0)
3. **Database Initialization File (`db.py`)**:
   - Provide a function `init_db()` that creates the above tables if they do not exist.
   - Provide helper functions to execute queries securely (preventing SQL injection).
