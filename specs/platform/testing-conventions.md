# Testing Conventions

## Metadata

| Field | Value |
|-------|-------|
| **Spec ID** | `platform/testing-conventions` |
| **Title** | Testing Conventions |
| **Layer** | Platform |
| **Status** | Draft |
| **Owner** | Platform Team |
| **Last Updated** | 2026-07-02 |
| **Depends On** | `platform/tech-stack` |
| **Extended By** | — |

---

## 1. Overview

This spec defines the testing strategy, tooling, conventions, and requirements for the entire product. Every feature spec's acceptance criteria must be verifiable through the testing patterns defined here.

**In scope:**
- Test frameworks and tooling per language/tier
- Test file structure and naming conventions
- Database isolation strategy for tests
- Test categories (unit, integration, e2e)
- Coverage requirements
- CI/CD test execution rules

**Out of scope:**
- Performance/load testing (see future `platform/performance-testing.md`)
- Security/penetration testing (see future `platform/security-testing.md`)
- Manual QA processes

---

## 2. Sealed Decisions

All testing decisions in this section are **🔒 Sealed**.

### 2.1 Test Frameworks

| Tier | Framework | Runner | Rationale |
|------|-----------|--------|-----------|
| **Python API** | **pytest** | pytest CLI | De facto Python standard; fixtures, parametrize, plugins |
| **React Frontend** | **Vitest** | Vitest CLI | Vite-native, Jest-compatible API, fast ESM support |
| **React Components** | **React Testing Library** | Via Vitest | Tests behavior, not implementation; encourages accessible markup |
| **E2E (cross-tier)** | **Playwright** | Playwright Test | Cross-browser, fast, reliable; runs against real Docker stack |

### 2.2 Core Rules

| Rule | Description |
|------|-------------|
| **Tests are mandatory** | No feature is considered "done" without tests covering its acceptance criteria. |
| **Tests run in CI** | Every pull request must pass all tests before merge. No exceptions. |
| **No production database in tests** | Tests MUST use isolated databases. Never connect to a real environment. |
| **Tests are deterministic** | No flaky tests. Tests must produce the same result on every run. Flaky tests are treated as bugs. |
| **Tests are independent** | Each test must set up and tear down its own state. No test depends on another test's output or execution order. |

---

## 3. Python API Testing

### 3.1 File Structure

```
api/
├── app/
│   ├── routers/
│   │   └── tasks.py
│   ├── services/
│   │   └── task_service.py
│   └── repositories/
│       └── task_repository.py
│
└── tests/
    ├── conftest.py              # Shared fixtures (test client, test DB, auth helpers)
    ├── unit/
    │   ├── services/
    │   │   └── test_task_service.py
    │   └── repositories/
    │       └── test_task_repository.py
    └── integration/
        └── routers/
            └── test_tasks_api.py
```

### 3.2 Naming Conventions

| Convention | Pattern | Example |
|-----------|---------|---------|
| Test files | `test_<module>.py` | `test_task_service.py` |
| Test functions | `test_<action>_<scenario>` | `test_create_task_with_valid_title` |
| Test classes (optional) | `Test<Entity><Action>` | `TestTaskCreation` |
| Fixtures | `<descriptive_name>` | `authenticated_client`, `sample_task` |

### 3.3 Database Isolation

Every test session gets a **fresh, isolated database**. This is the pattern extracted from the original spec's approach of using a temporary database per test:

```python
# tests/conftest.py

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.main import app
from fastapi.testclient import TestClient

# 🔒 Sealed: Tests MUST use a separate database, never the production one.
TEST_DATABASE_URL = "mysql+pymysql://root:test@localhost:3307/test_db"

@pytest.fixture(scope="session")
def engine():
    """Create a test database engine (once per test session)."""
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()

@pytest.fixture(scope="function")
def db_session(engine):
    """Create a fresh database session per test, rolled back after each test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()

    yield session

    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture
def client(db_session):
    """FastAPI test client with dependency injection for the DB session."""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()

@pytest.fixture
def authenticated_client(client, db_session):
    """Test client with a valid auth token for a test user."""
    # Create a test user and generate a token
    user = create_test_user(db_session)
    token = generate_test_token(user.id)
    client.headers["Authorization"] = f"Bearer {token}"
    yield client
```

### 3.4 Docker Test Database

When running tests inside Docker, a dedicated test database container is used:

```yaml
# docker-compose.test.yml
services:
  test-db:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: test
      MYSQL_DATABASE: test_db
    ports:
      - "3307:3306"
    tmpfs:
      - /var/lib/mysql    # In-memory for speed — data is not persisted
```

> **🔒 Sealed:** Test database uses `tmpfs` (in-memory storage) for speed. Test data is never persisted between runs.

### 3.5 Test Categories

| Category | Scope | Database | External Services | Speed Target |
|----------|-------|----------|-------------------|-------------|
| **Unit** | Single function/class | Mocked | Mocked | < 1s per test |
| **Integration** | API endpoint → DB | Real (test DB) | Mocked | < 3s per test |
| **E2E** | Browser → API → DB | Real (test DB) | Real or mocked | < 10s per test |

### 3.6 Running Tests

```bash
# All Python tests
docker-compose exec api pytest

# Unit tests only
docker-compose exec api pytest tests/unit/

# Integration tests only
docker-compose exec api pytest tests/integration/

# With coverage
docker-compose exec api pytest --cov=app --cov-report=term-missing

# Specific test file
docker-compose exec api pytest tests/integration/routers/test_tasks_api.py

# Verbose with print output
docker-compose exec api pytest -v -s
```

---

## 4. React Frontend Testing

### 4.1 File Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── TaskCard.tsx
│   │   └── __tests__/
│   │       └── TaskCard.test.tsx
│   ├── pages/
│   │   ├── TaskListPage.tsx
│   │   └── __tests__/
│   │       └── TaskListPage.test.tsx
│   ├── hooks/
│   │   ├── useTasks.ts
│   │   └── __tests__/
│   │       └── useTasks.test.ts
│   └── services/
│       ├── taskService.ts
│       └── __tests__/
│           └── taskService.test.ts
│
└── e2e/
    └── tasks.spec.ts           # Playwright E2E tests
```

### 4.2 Naming Conventions

| Convention | Pattern | Example |
|-----------|---------|---------|
| Test files | `<ComponentName>.test.tsx` | `TaskCard.test.tsx` |
| Test blocks | `describe('<Component>', () => ...)` | `describe('TaskCard', () => ...)` |
| Test cases | `it('should <behavior>')` | `it('should mark task as completed on click')` |

### 4.3 Component Testing Pattern

```tsx
// src/components/__tests__/TaskCard.test.tsx

import { render, screen, fireEvent } from '@testing-library/react';
import { TaskCard } from '../TaskCard';

describe('TaskCard', () => {
  const mockTask = {
    id: '123',
    title: 'Buy groceries',
    is_completed: false,
    priority: 'high',
    due_date: '2026-07-10',
  };

  it('should display the task title', () => {
    render(<TaskCard task={mockTask} onToggle={vi.fn()} onDelete={vi.fn()} />);
    expect(screen.getByText('Buy groceries')).toBeInTheDocument();
  });

  it('should call onToggle when checkbox is clicked', () => {
    const onToggle = vi.fn();
    render(<TaskCard task={mockTask} onToggle={onToggle} onDelete={vi.fn()} />);
    fireEvent.click(screen.getByRole('checkbox'));
    expect(onToggle).toHaveBeenCalledWith('123');
  });

  it('should call onDelete when delete button is clicked', () => {
    const onDelete = vi.fn();
    render(<TaskCard task={mockTask} onToggle={vi.fn()} onDelete={onDelete} />);
    fireEvent.click(screen.getByRole('button', { name: /delete/i }));
    expect(onDelete).toHaveBeenCalledWith('123');
  });
});
```

### 4.4 API Mocking

```tsx
// Use MSW (Mock Service Worker) for API mocking in frontend tests.
// 🔒 Sealed: Frontend tests MUST NOT call real API endpoints.

import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

const server = setupServer(
  http.get('/api/tasks', () => {
    return HttpResponse.json({
      data: [{ id: '1', title: 'Test task', is_completed: false }],
      pagination: { page: 1, page_size: 25, total_items: 1, total_pages: 1 },
    });
  }),
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

### 4.5 Running Tests

```bash
# All frontend tests
docker-compose exec frontend npm test

# Watch mode (dev)
docker-compose exec frontend npm test -- --watch

# With coverage
docker-compose exec frontend npm test -- --coverage
```

---

## 5. End-to-End Testing

### 5.1 Setup

E2E tests run against the full Docker Compose stack (frontend + API + database).

```bash
# Run E2E tests
npx playwright test

# With UI mode (headed browser)
npx playwright test --ui

# Specific test file
npx playwright test e2e/tasks.spec.ts
```

### 5.2 E2E Test Pattern

```typescript
// frontend/e2e/tasks.spec.ts

import { test, expect } from '@playwright/test';

test.describe('Task Management', () => {
  test.beforeEach(async ({ page }) => {
    // Login with test credentials
    await page.goto('/login');
    await page.fill('[name="email"]', 'testuser@example.com');
    await page.fill('[name="password"]', 'TestPass123!');
    await page.click('button[type="submit"]');
    await page.waitForURL('/tasks');
  });

  test('should create a new task', async ({ page }) => {
    await page.fill('[name="title"]', 'E2E Test Task');
    await page.click('button:has-text("Add")');
    await expect(page.locator('text=E2E Test Task')).toBeVisible();
  });

  test('should toggle task completion', async ({ page }) => {
    const checkbox = page.locator('[role="checkbox"]').first();
    await checkbox.click();
    await expect(checkbox).toBeChecked();
  });

  test('should delete a task', async ({ page }) => {
    const taskTitle = page.locator('.task-title').first();
    const title = await taskTitle.textContent();
    await page.locator('[aria-label="Delete task"]').first().click();
    await page.click('button:has-text("Confirm")');
    await expect(page.locator(`text=${title}`)).not.toBeVisible();
  });
});
```

---

## 6. Coverage Requirements

### 🔧 Configurable

| Metric | Minimum | Target | Config Key |
|--------|---------|--------|------------|
| Python API line coverage | 80% | 90%+ | `test_python_min_coverage` |
| React component coverage | 70% | 85%+ | `test_frontend_min_coverage` |
| E2E critical path coverage | 100% of acceptance criteria | — | — |

> **🔒 Sealed:** Coverage gates are enforced in CI. A PR cannot merge if coverage drops below the minimum threshold.

### What Must Be Tested

| Layer | Must Test | Can Skip |
|-------|-----------|----------|
| API routers | Every endpoint: success + each error case | — |
| Services | All business logic branches | Simple pass-through methods |
| Repositories | Complex queries, edge cases | Simple CRUD (covered by integration tests) |
| React components | User interactions, conditional rendering | Pure styling components with no logic |
| Hooks | State changes, API call triggers | — |

---

## 7. CI/CD Integration

### 🔒 Sealed Rules

| Rule | Description |
|------|-------------|
| **Tests run on every PR** | No exceptions. All test categories execute. |
| **Tests must pass to merge** | Failing tests block the merge. No manual overrides. |
| **Coverage is tracked** | Coverage reports are generated and compared against thresholds. |
| **Test DB is ephemeral** | CI uses a fresh MySQL container per run. No shared test databases. |

### CI Pipeline Order

```
1. Lint (Python: ruff/flake8, TypeScript: ESLint)
2. Type check (Python: mypy, TypeScript: tsc --noEmit)
3. Unit tests (parallel: Python + React)
4. Integration tests (Python API + test DB)
5. Build (React production build)
6. E2E tests (Playwright against Docker stack)
7. Coverage report
```

---

## 8. Acceptance Criteria

| AC | Criteria |
|----|----------|
| AC-01 | `docker-compose exec api pytest` runs all Python tests with zero failures. |
| AC-02 | `docker-compose exec frontend npm test` runs all frontend tests with zero failures. |
| AC-03 | Each test uses an isolated database session — no test pollutes another's state. |
| AC-04 | Python API coverage meets the configured minimum (default: 80%). |
| AC-05 | Frontend component coverage meets the configured minimum (default: 70%). |
| AC-06 | E2E tests cover all acceptance criteria from core feature specs. |
| AC-07 | CI pipeline runs all tests on every PR and blocks merge on failure. |
| AC-08 | A new developer can run the full test suite with a single command after `docker-compose up`. |

---

## 9. Open Questions

| # | Question | Status | Resolution |
|---|----------|--------|------------|
| Q1 | Should we use a shared test fixtures package between unit and integration tests, or keep them separate? | Open | |
| Q2 | Do we need visual regression testing for the React frontend (e.g., Playwright screenshots)? | Open | |
| Q3 | Should we adopt mutation testing (e.g., `mutmut` for Python) to validate test quality? | Open | |

---

## Changelog

| Date | Change |
|------|--------|
| 2026-07-02 | Initial draft — extracted testing patterns from legacy spec, adapted for FastAPI + React + Docker stack |
