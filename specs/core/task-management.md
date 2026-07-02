# Task Management

## Metadata

| Field | Value |
|-------|-------|
| **Spec ID** | `core/task-management` |
| **Title** | Task Management |
| **Layer** | Core |
| **Status** | Draft |
| **Owner** | Product Team |
| **Last Updated** | 2026-07-02 |
| **Depends On** | `platform/tech-stack`, `platform/database-conventions`, `platform/api-conventions`, `core/auth-login` |
| **Extended By** | — |

---

## 1. Overview

This spec defines how users create, view, update, and delete tasks within the application. Tasks are the primary unit of work — each task has a title, optional description, completion status, priority, and due date. Tasks are scoped to authenticated users (each user sees only their own tasks).

**In scope:**
- Task CRUD (create, read, update, delete)
- Task completion toggling
- Task listing with filtering, sorting, and pagination
- Task priority and due dates
- Per-user task ownership and isolation

**Out of scope:**
- Team/shared task boards (future extension)
- Recurring tasks (future extension)
- Task assignments to other users (future extension)
- Subtasks / task hierarchies (future extension)
- File attachments on tasks (future extension)

---

## 2. User Stories

| ID | Story | Priority |
|----|-------|----------|
| US-01 | As a user, I want to add a task with a title, so that I can track work I need to do. | Must |
| US-02 | As a user, I want to see all my tasks on a single page, so that I have a clear view of my workload. | Must |
| US-03 | As a user, I want to mark a task as complete, so that I can track my progress. | Must |
| US-04 | As a user, I want to delete a task, so that I can remove items I no longer need. | Must |
| US-05 | As a user, I want to edit a task's title and description, so that I can refine my tasks after creation. | Must |
| US-06 | As a user, I want to set a priority on my tasks (low, medium, high), so that I can focus on what matters most. | Should |
| US-07 | As a user, I want to set a due date on a task, so that I can track deadlines. | Should |
| US-08 | As a user, I want to filter tasks by status (all, active, completed), so that I can focus on what's relevant. | Should |
| US-09 | As a user, I want to sort tasks by creation date, due date, or priority, so that I can organize my view. | Could |
| US-10 | As a user, I want my tasks to persist across sessions, so that I don't lose my data. | Must |

---

## 3. Data Model

### 3.1 Entity: `tasks`

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PK, auto-generated | |
| `user_id` | UUID | FK → `users.id`, NOT NULL, ON DELETE CASCADE | Task owner — enforces per-user isolation |
| `title` | VARCHAR(255) | NOT NULL | Required, trimmed, max 255 chars |
| `description` | TEXT | NULLABLE | Optional long-form details |
| `is_completed` | BOOLEAN | NOT NULL, DEFAULT false | Toggle via dedicated endpoint |
| `priority` | ENUM('low', 'medium', 'high') | NOT NULL, DEFAULT 'medium' | Sortable |
| `due_date` | DATE | NULLABLE | Optional deadline, no time component |
| `completed_at` | TIMESTAMP | NULLABLE | Auto-set when `is_completed` → true, cleared when toggled back |
| `created_at` | TIMESTAMP | NOT NULL, auto-set | |
| `updated_at` | TIMESTAMP | NOT NULL, auto-updated | |

### 3.2 Relationships

- `users` → `tasks` (one-to-many via `user_id` FK)

### 3.3 Indexes

| Index | Columns | Type | Rationale |
|-------|---------|------|-----------|
| `idx_tasks_user_id` | `user_id` | BTREE | All queries are scoped by user |
| `idx_tasks_user_status` | `user_id, is_completed` | BTREE | Filter by active/completed |
| `idx_tasks_user_due` | `user_id, due_date` | BTREE | Sort by due date |
| `idx_tasks_user_priority` | `user_id, priority` | BTREE | Sort by priority |

### 3.4 SQLAlchemy Model (Reference)

```python
class Task(Base):
    __tablename__ = "tasks"

    id = Column(UUID, primary_key=True, default=uuid4)
    user_id = Column(UUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_completed = Column(Boolean, nullable=False, default=False)
    priority = Column(Enum("low", "medium", "high", name="task_priority"), nullable=False, default="medium")
    due_date = Column(Date, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationship
    owner = relationship("User", back_populates="tasks")
```

---

## 4. API Contract

> All endpoints require authentication via `Authorization: Bearer <access_token>` header.
> All endpoints are scoped to the authenticated user — a user can never access another user's tasks.

### 4.1 `POST /api/tasks`

**Purpose:** Create a new task.

**Request:**
```json
{
  "title": "Buy groceries",
  "description": "Milk, eggs, bread",
  "priority": "high",
  "due_date": "2026-07-10"
}
```

> Only `title` is required. `description`, `priority`, and `due_date` are optional.

**Response (201):**
```json
{
  "id": "uuid",
  "title": "Buy groceries",
  "description": "Milk, eggs, bread",
  "is_completed": false,
  "priority": "high",
  "due_date": "2026-07-10",
  "completed_at": null,
  "created_at": "2026-07-02T12:00:00Z",
  "updated_at": "2026-07-02T12:00:00Z"
}
```

**Errors:**

| Status | Code | Description |
|--------|------|-------------|
| 400 | `VALIDATION_ERROR` | Title missing, empty, or exceeds 255 chars |
| 400 | `INVALID_PRIORITY` | Priority not one of: low, medium, high |
| 400 | `INVALID_DATE` | Due date is not a valid date format |
| 401 | `UNAUTHORIZED` | Missing or invalid auth token |

---

### 4.2 `GET /api/tasks`

**Purpose:** List all tasks for the authenticated user, with optional filtering, sorting, and pagination.

**Query Parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `status` | string | `all` | Filter: `all`, `active`, `completed` |
| `priority` | string | — | Filter: `low`, `medium`, `high` |
| `sort` | string | `created_at` | Sort field: `created_at`, `due_date`, `priority`, `updated_at` |
| `order` | string | `desc` | Sort order: `asc`, `desc` |
| `page` | int | 1 | Page number (1-indexed) |
| `page_size` | int | 25 | Items per page (🔧 Configurable, max 100) |

**Response (200):**
```json
{
  "data": [
    {
      "id": "uuid",
      "title": "Buy groceries",
      "description": "Milk, eggs, bread",
      "is_completed": false,
      "priority": "high",
      "due_date": "2026-07-10",
      "completed_at": null,
      "created_at": "2026-07-02T12:00:00Z",
      "updated_at": "2026-07-02T12:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 25,
    "total_items": 42,
    "total_pages": 2
  }
}
```

**Errors:**

| Status | Code | Description |
|--------|------|-------------|
| 400 | `INVALID_PARAMETER` | Invalid sort field, order, or filter value |
| 401 | `UNAUTHORIZED` | Missing or invalid auth token |

---

### 4.3 `GET /api/tasks/{task_id}`

**Purpose:** Get a single task by ID.

**Response (200):**
```json
{
  "id": "uuid",
  "title": "Buy groceries",
  "description": "Milk, eggs, bread",
  "is_completed": false,
  "priority": "high",
  "due_date": "2026-07-10",
  "completed_at": null,
  "created_at": "2026-07-02T12:00:00Z",
  "updated_at": "2026-07-02T12:00:00Z"
}
```

**Errors:**

| Status | Code | Description |
|--------|------|-------------|
| 401 | `UNAUTHORIZED` | Missing or invalid auth token |
| 404 | `TASK_NOT_FOUND` | Task does not exist or belongs to another user |

> **Security:** Return 404 (not 403) when the task belongs to another user — prevent enumeration.

---

### 4.4 `PATCH /api/tasks/{task_id}`

**Purpose:** Update a task's title, description, priority, or due date.

**Request (partial update):**
```json
{
  "title": "Buy groceries and snacks",
  "priority": "medium"
}
```

> Only include fields being changed. Omitted fields remain unchanged.

**Response (200):** Full task object (same shape as GET).

**Errors:**

| Status | Code | Description |
|--------|------|-------------|
| 400 | `VALIDATION_ERROR` | Title empty or exceeds 255 chars |
| 401 | `UNAUTHORIZED` | Missing or invalid auth token |
| 404 | `TASK_NOT_FOUND` | Task does not exist or belongs to another user |

> **Note:** `is_completed` cannot be set via PATCH — use the dedicated toggle endpoint (4.5) instead. This prevents accidental completion during edits.

---

### 4.5 `POST /api/tasks/{task_id}/toggle`

**Purpose:** Toggle the completion status of a task.

**Request:** No body required.

**Response (200):**
```json
{
  "id": "uuid",
  "is_completed": true,
  "completed_at": "2026-07-02T14:30:00Z"
}
```

**Behavior:**
- If `is_completed` is false → set to true, set `completed_at` to now.
- If `is_completed` is true → set to false, clear `completed_at` to null.

**Errors:**

| Status | Code | Description |
|--------|------|-------------|
| 401 | `UNAUTHORIZED` | Missing or invalid auth token |
| 404 | `TASK_NOT_FOUND` | Task does not exist or belongs to another user |

---

### 4.6 `DELETE /api/tasks/{task_id}`

**Purpose:** Permanently delete a task.

**Response (204):** No content.

**Errors:**

| Status | Code | Description |
|--------|------|-------------|
| 401 | `UNAUTHORIZED` | Missing or invalid auth token |
| 404 | `TASK_NOT_FOUND` | Task does not exist or belongs to another user |

> **Note:** This is a hard delete, not soft delete. Task data is permanently removed.

---

## 5. UI Behavior

### 5.1 Screen: Task List (Main View)

**Layout:**
- **Top:** Add task form — title input, optional priority dropdown, optional due date picker, "Add" button.
- **Middle:** Filter bar — status tabs (All / Active / Completed), sort dropdown.
- **Bottom:** Task list — cards or rows showing title, priority badge, due date, completion checkbox, delete button.
- **Footer:** Pagination controls.

**Flow:**
1. Page loads → fetch `GET /api/tasks` with default params.
2. User types title + clicks "Add" → `POST /api/tasks` → new task appears at top of list.
3. User clicks checkbox → `POST /api/tasks/{id}/toggle` → task visually toggles (strikethrough if completed).
4. User clicks task title → inline edit mode or detail panel → `PATCH /api/tasks/{id}` on save.
5. User clicks delete icon → confirmation dialog → `DELETE /api/tasks/{id}` → task removed from list.
6. User clicks filter tab → re-fetch with `status` param.
7. User changes sort → re-fetch with `sort` + `order` params.

**States:**

| State | Behavior |
|-------|----------|
| Loading | Show skeleton cards / spinner |
| Empty (no tasks) | Show empty-state illustration: "No tasks yet. Add one above!" |
| Empty (filtered) | Show "No matching tasks" with option to clear filters |
| Error | Show error banner with retry button |
| Optimistic updates | Toggle and delete apply immediately; revert on API failure |

### 5.2 Inline Validation

| Field | Rule | Error Message |
|-------|------|---------------|
| Title | Required, 1–255 chars | "Title is required" / "Title must be under 255 characters" |
| Priority | Must be low/medium/high | "Select a valid priority" |
| Due date | Must be a valid date (past dates allowed) | "Enter a valid date" |

---

## 6. Business Rules

| Rule | Description | Mutability |
|------|-------------|------------|
| BR-01 | Every task belongs to exactly one user. Users can only see/modify their own tasks. | 🔒 Sealed |
| BR-02 | Task title is required and cannot be empty or whitespace-only. | 🔒 Sealed |
| BR-03 | Deletes are permanent (hard delete). No soft-delete or trash. | 🔧 Configurable |
| BR-04 | Toggling completion is a dedicated action, not part of general update. | 🔒 Sealed |
| BR-05 | `completed_at` is system-managed — auto-set on toggle, not user-editable. | 🔒 Sealed |
| BR-06 | Default sort order is newest first (`created_at DESC`). | 🔧 Configurable |
| BR-07 | Default page size for task list. | 🔧 Configurable |
| BR-08 | Task fields beyond the standard set can be added. | 🔌 Extensible |
| BR-09 | Actions after task completion can be extended (e.g., notifications, gamification). | 🔌 Extensible |

---

## 7. Mutability Decisions

### 🔒 Sealed (cannot be changed)

| Decision | Rationale |
|----------|-----------|
| Tasks are user-scoped (no cross-user access) | Fundamental data isolation; changing this alters the security model |
| Title is required, max 255 chars | Core data integrity; empty tasks are meaningless |
| Completion toggle is a dedicated endpoint | Prevents accidental completion during edits; cleaner audit trail |
| `completed_at` is auto-managed | Timestamp accuracy; user cannot backdate completions |
| 404 returned for other users' tasks (not 403) | Prevents task ID enumeration across users |

### 🔧 Configurable (tunable within bounds)

| Decision | Default | Range | Config Key |
|----------|---------|-------|------------|
| Default page size | 25 | 10–100 | `tasks_default_page_size` |
| Max title length | 255 | 100–500 | `tasks_max_title_length` |
| Default sort field | `created_at` | Any valid sort field | `tasks_default_sort` |
| Default sort order | `desc` | `asc`, `desc` | `tasks_default_order` |
| Soft delete instead of hard delete | false | true/false | `tasks_soft_delete_enabled` |
| Max tasks per user | unlimited | 100–10,000 or unlimited | `tasks_max_per_user` |

### 🔌 Extensible (can be extended, core preserved)

| Hook Point | What Can Be Added | What Cannot Change |
|-----------|-------------------|-------------------|
| Task fields | Custom fields (tags, category, assignee) alongside standard ones | Standard fields (title, is_completed, priority, due_date) cannot be removed |
| Post-completion actions | Notifications, gamification points, workflow triggers | Core toggle behavior and `completed_at` management is fixed |
| Pre-delete validation | Confirmation requirements, archive-instead-of-delete | If delete proceeds, the task must be fully removed (or soft-deleted per config) |
| List view columns | Additional columns in the task list UI | Title, status checkbox, and delete action must always be visible |

---

## 8. Acceptance Criteria

| AC | Criteria | Covers |
|----|----------|--------|
| AC-01 | Given I am logged in, when I submit a title in the add form, then a new task appears in my list with status "active". | US-01 |
| AC-02 | Given I have tasks, when I load the task list page, then I see all my tasks with title, status, priority, and due date. | US-02 |
| AC-03 | Given an active task, when I click the completion checkbox, then the task shows as completed with a `completed_at` timestamp. | US-03 |
| AC-04 | Given a task, when I click delete and confirm, then the task is permanently removed from the list and database. | US-04 |
| AC-05 | Given a task, when I edit the title and save, then the updated title is persisted and `updated_at` is refreshed. | US-05 |
| AC-06 | Given tasks with different priorities, when I sort by priority, then tasks are ordered high → medium → low (or reverse). | US-06, US-09 |
| AC-07 | Given I set a due date on a task, when I view the task list, then the due date is displayed alongside the task. | US-07 |
| AC-08 | Given a mix of active and completed tasks, when I filter by "active", then only incomplete tasks are shown. | US-08 |
| AC-09 | Given I log out and log back in, when I view tasks, then all my previously created tasks are still present. | US-10 |
| AC-10 | Given I am user A, when I try to access user B's task by ID, then I receive a 404 (not 403). | BR-01 |

---

## 9. Non-Functional Requirements

| Requirement | Target | Notes |
|-------------|--------|-------|
| Task list response time | < 200ms p95 | With up to 1,000 tasks per user |
| Task creation response time | < 150ms p95 | Single INSERT |
| Toggle response time | < 100ms p95 | Single UPDATE |
| Concurrent users | 100+ | Per-tenant; connection pooling handles this |
| Data integrity | Zero data loss | All writes are transactional |
| Accessibility | WCAG 2.1 AA | Checkboxes, buttons, and forms must be keyboard-navigable |

---

## 10. Open Questions

| # | Question | Status | Resolution |
|---|----------|--------|------------|
| Q1 | Should we add a "due today" / "overdue" visual indicator on the task list? | Open | |
| Q2 | Should completed tasks be auto-archived after N days? | Open | Candidate for extension |
| Q3 | Do we need bulk actions (complete all, delete all completed)? | Open | |
| Q4 | Should the task list support drag-and-drop reordering? | Open | Would require a `position` column |

---

## Changelog

| Date | Change |
|------|--------|
| 2026-07-02 | Initial draft — converted from legacy Flask/SQLite spec to sealed tech stack (React + FastAPI + MySQL) |
