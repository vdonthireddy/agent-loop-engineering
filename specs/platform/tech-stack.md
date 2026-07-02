# Technology Stack

## Metadata

| Field | Value |
|-------|-------|
| **Spec ID** | `platform/tech-stack` |
| **Title** | Technology Stack |
| **Layer** | Platform |
| **Status** | Approved |
| **Owner** | Platform Team |
| **Last Updated** | 2026-07-02 |
| **Depends On** | — (foundational spec, no dependencies) |
| **Extended By** | — |

---

## 1. Overview

This spec defines the languages, frameworks, runtimes, and core libraries used across the entire product. These choices are **🔒 Sealed** — they represent architectural commitments that all features, agents, and extensions must respect.

**In scope:**
- Frontend framework and runtime
- Backend frameworks and languages
- Database engine and ORM
- Package management and build tooling
- Runtime versions and compatibility targets

**Out of scope:**
- API design patterns (see `platform/api-conventions.md`)
- Authentication architecture (see `platform/auth-architecture.md`)
- Database naming and migration strategy (see `platform/database-conventions.md`)
- UI component library and design tokens (see `platform/ui-design-system.md`)
- CI/CD and deployment (see `platform/infrastructure.md`)

---

## 2. Architecture Overview

The product follows a **three-tier architecture** with a clear separation between the frontend client, backend API services, and the data layer.

```
┌──────────────────────────────────────────────────────────────┐
│                        CLIENT TIER                            │
│                                                                │
│   React 18+ (SPA)                                             │
│   ├── Vite (build + dev server)                               │
│   ├── React Router (client-side routing)                      │
│   └── Axios or Fetch API (HTTP client)                        │
│                                                                │
├──────────────────────────────────────────────────────────────┤
│                       SERVICE TIER                             │
│                                                                │
│   Node.js 20 LTS                        Python 3.11+          │
│   ├── Express / API Gateway             ├── FastAPI            │
│   ├── Auth middleware                    ├── SQLAlchemy 2.0     │
│   ├── Request routing                   ├── Pydantic v2        │
│   └── Static file serving               └── Alembic            │
│                                           (migrations)         │
│                                                                │
├──────────────────────────────────────────────────────────────┤
│                        DATA TIER                               │
│                                                                │
│   MySQL 8.0+                                                   │
│   └── InnoDB engine (default)                                  │
│                                                                │
└──────────────────────────────────────────────────────────────┘
```

### Service Tier Responsibilities

| Service | Language | Role |
|---------|----------|------|
| **API Gateway / BFF** | Node.js | Request routing, auth middleware, session management, static file serving, frontend SSR (if needed) |
| **Core API** | Python (FastAPI) | Business logic, data access, CRUD operations, background tasks, AI/ML integrations |

> **Why two backend runtimes?**
> - **Node.js** handles the edge: auth middleware, API gateway, real-time features (WebSocket), and serves the React frontend.
> - **Python (FastAPI)** handles the core: business logic, data processing, and AI/ML integrations where the Python ecosystem excels.
> - This is a common BFF (Backend-for-Frontend) pattern. If the project starts simple, the Node.js layer can be omitted and React can call FastAPI directly.

---

## 3. Sealed Decisions

All decisions in this section are **🔒 Sealed**. Agents and developers MUST NOT generate code that contradicts any of these.

### 3.1 Frontend

| Decision | Value | Rationale |
|----------|-------|-----------|
| Frontend framework | **React 18+** | Component-based UI, massive ecosystem, strong hiring pool |
| Language | **TypeScript** (preferred) / JavaScript | Type safety reduces bugs; JS allowed for scripts and config |
| Build tool | **Vite 5+** | Fast HMR, ESM-native, superior DX over Webpack |
| Routing | **React Router v6+** | De facto standard for React SPAs |
| State management | Team's choice (Zustand, Redux Toolkit, or Context) | Sealed as "must use one of these three"; specific choice is per-project |
| Package manager | **npm** | Consistency across frontend and Node.js layers |

### 3.2 Backend — Node.js

| Decision | Value | Rationale |
|----------|-------|-----------|
| Runtime | **Node.js 20 LTS** | Long-term support, stable APIs |
| Language | **TypeScript** (preferred) / JavaScript | Type safety for API contracts |
| Framework | **Express 4+** (or **Fastify** if perf-critical) | Minimal, flexible, well-understood |
| Package manager | **npm** | Matches frontend |

### 3.3 Backend — Python

| Decision | Value | Rationale |
|----------|-------|-----------|
| Runtime | **Python 3.11+** | Performance improvements, modern syntax (match/case, exception groups) |
| Framework | **FastAPI 0.100+** | Async-native, auto-generated OpenAPI docs, Pydantic integration |
| ORM | **SQLAlchemy 2.0** | Industry-standard Python ORM, 2.0 style with type hints |
| Schema validation | **Pydantic v2** | Built into FastAPI; used for request/response models |
| Migrations | **Alembic** | SQLAlchemy-native migration tool |
| Package manager | **pip** with `requirements.txt` or **Poetry** | Team's choice; sealed as "must use one of these two" |
| Virtual environment | **venv** or **virtualenv** | Required for all Python development; no global installs |

### 3.4 Database

| Decision | Value | Rationale |
|----------|-------|-----------|
| Database engine | **MySQL 8.0+** | Mature, reliable, strong cloud support (RDS, Cloud SQL, PlanetScale) |
| Storage engine | **InnoDB** | ACID transactions, row-level locking, FK constraints |
| Character set | **utf8mb4** | Full Unicode support (including emoji) |
| Collation | **utf8mb4_unicode_ci** | Case-insensitive, accent-insensitive by default |

### 3.5 API Communication

| Decision | Value | Rationale |
|----------|-------|-----------|
| API format | **REST + JSON** | Simple, well-understood, debuggable |
| Internal service communication | **HTTP REST** (Node.js ↔ FastAPI) | Keep it simple; gRPC only if latency proves problematic |
| API documentation | **OpenAPI 3.1** (auto-generated by FastAPI) | Single source of truth for API contracts |

### 3.6 Containerization & Infrastructure

| Decision | Value | Rationale |
|----------|-------|----------|
| Container runtime | **Docker** | Industry standard; consistent dev/staging/prod environments |
| Local orchestration | **Docker Compose** | Multi-service local dev with a single `docker-compose up` |
| Every service has a Dockerfile | **Required** | No service runs outside a container in any environment |
| Base images | **Official slim variants** (e.g., `node:20-slim`, `python:3.11-slim`) | Minimal attack surface, smaller image sizes |
| Multi-stage builds | **Required for production** | Separate build and runtime stages to reduce final image size |
| `.dockerignore` | **Required per service** | Prevent `node_modules`, `.venv`, `.git`, etc. from entering images |

---

## 4. Configurable Decisions

These have sensible defaults but can be adjusted per project or deployment.

| Decision | Default | Range | Config Key |
|----------|---------|-------|------------|
| Node.js port | 3000 | 1024–65535 | `NODE_PORT` |
| FastAPI port | 8000 | 1024–65535 | `API_PORT` |
| MySQL port | 3306 | 1024–65535 | `DB_PORT` |
| MySQL connection pool size | 10 | 5–50 | `DB_POOL_SIZE` |
| MySQL connection pool overflow | 20 | 10–100 | `DB_POOL_MAX_OVERFLOW` |
| Log level | `INFO` | DEBUG, INFO, WARNING, ERROR | `LOG_LEVEL` |
| CORS allowed origins | `["http://localhost:5173"]` | Any valid origin list | `CORS_ORIGINS` |

---

## 5. Version Pinning Policy

| Rule | Description |
|------|-------------|
| **Major versions are sealed** | Changing React 18 → 19 or Python 3.11 → 3.12 requires a spec amendment |
| **Minor/patch updates are allowed** | Security patches and bug fixes can be applied without spec changes |
| **Lock files are required** | `package-lock.json` (npm) and `requirements.txt` with pinned versions must be committed |
| **No floating versions** | `"react": "^18.2.0"` is acceptable; `"react": "*"` or `"latest"` is not |

---

## 6. Project Structure (Reference)

```
project-root/
│
├── frontend/                    # React application
│   ├── public/
│   ├── src/
│   │   ├── components/          # Reusable UI components
│   │   ├── pages/               # Route-level page components
│   │   ├── hooks/               # Custom React hooks
│   │   ├── services/            # API client modules
│   │   ├── stores/              # State management
│   │   ├── utils/               # Shared utilities
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── Dockerfile               # Multi-stage: build + nginx serve
│   ├── .dockerignore
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.json
│
├── gateway/                     # Node.js API gateway (optional)
│   ├── src/
│   │   ├── middleware/          # Auth, logging, rate limiting
│   │   ├── routes/             # Route definitions
│   │   └── index.ts
│   ├── Dockerfile               # Multi-stage: build + node runtime
│   ├── .dockerignore
│   ├── package.json
│   └── tsconfig.json
│
├── api/                         # Python FastAPI service
│   ├── app/
│   │   ├── models/             # SQLAlchemy models
│   │   ├── schemas/            # Pydantic request/response models
│   │   ├── routers/            # API route handlers
│   │   ├── services/           # Business logic
│   │   ├── repositories/       # Data access layer
│   │   ├── core/               # Config, security, dependencies
│   │   └── main.py
│   ├── alembic/                # Database migrations
│   ├── tests/
│   ├── Dockerfile               # Multi-stage: deps + uvicorn runtime
│   ├── .dockerignore
│   ├── requirements.txt
│   └── alembic.ini
│
├── specs/                       # Specification documents
│   ├── SPEC_FRAMEWORK.md
│   ├── SPEC_TEMPLATE.md
│   ├── platform/
│   ├── core/
│   └── extensions/
│
├── docker-compose.yml           # Full local stack (all services + MySQL)
├── docker-compose.override.yml  # Dev overrides (volumes, hot-reload)
├── .env.example                 # Environment variable template
└── README.md
```

> **Note:** The `gateway/` layer is optional. For simpler projects, the React frontend can call the FastAPI service directly. Introduce the Node.js gateway when you need auth middleware, request aggregation, or real-time WebSocket features.

---

## 7. Development Environment

### Required Tools

| Tool | Version | Purpose |
|------|---------|---------|
| Docker | 24+ | Container runtime for all services |
| Docker Compose | v2+ | Multi-service local orchestration |
| Git | 2.40+ | Version control |

> **Note:** Node.js, Python, and MySQL are **not required locally** — they run inside containers. Install them locally only if you prefer running individual services outside Docker for debugging.

### Recommended Tools

| Tool | Purpose |
|------|---------|
| Node.js 20 LTS + npm | Local frontend dev with faster HMR (outside container) |
| Python 3.11+ + pip | Local API dev with debugger attach |
| VS Code / Cursor | IDE with TypeScript + Python support |
| Postman or Bruno | API testing |
| MySQL Workbench or DBeaver | Database management |

---

## 8. Containerization

### 🔒 Sealed Rules

| Rule | Description |
|------|-------------|
| **All services containerized** | Every service (frontend, gateway, API, database) runs in a Docker container. No exceptions. |
| **Single-command startup** | `docker-compose up` must start the entire stack from a cold clone. |
| **No host dependencies** | A new developer needs ONLY Docker and Git installed. Nothing else. |
| **Environment via `.env`** | All config passed via environment variables. No hardcoded connection strings, ports, or secrets in Dockerfiles. |
| **Health checks required** | Every service container must define a `healthcheck` in `docker-compose.yml`. |
| **Named volumes for persistence** | MySQL data uses a named Docker volume. No bind-mounts for database storage. |

### Docker Compose Services

| Service | Image / Build | Ports | Depends On |
|---------|--------------|-------|------------|
| `frontend` | `./frontend` | `5173:5173` (dev) / `80:80` (prod) | `api` |
| `gateway` | `./gateway` (optional) | `3000:3000` | `api` |
| `api` | `./api` | `8000:8000` | `db` |
| `db` | `mysql:8.0` | `3306:3306` | — |

### Development Workflow

```bash
# First-time setup (cold clone)
git clone <repo-url> && cd <project>
cp .env.example .env
docker-compose up --build

# Daily development
docker-compose up              # Start all services
docker-compose up -d           # Start in background
docker-compose logs -f api     # Tail API logs
docker-compose exec api bash   # Shell into API container

# Database migrations
docker-compose exec api alembic upgrade head

# Rebuild after dependency changes
docker-compose up --build api

# Tear down
docker-compose down            # Stop containers
docker-compose down -v         # Stop + remove volumes (reset DB)
```

### Hot-Reload in Development

| Service | Strategy |
|---------|----------|
| `frontend` | Bind-mount `./frontend/src` → container; Vite HMR handles reloads |
| `gateway` | Bind-mount `./gateway/src` → container; `nodemon` or `tsx --watch` |
| `api` | Bind-mount `./api/app` → container; `uvicorn --reload` |
| `db` | No reload needed; data persists in named volume |

> Hot-reload mounts are defined in `docker-compose.override.yml` (dev only) and are NOT used in production builds.

---

## 9. Acceptance Criteria

| AC | Criteria |
|----|----------|
| AC-01 | A new developer can run `docker-compose up` from a cold clone and have the entire stack running. |
| AC-02 | No local Node.js, Python, or MySQL installation is required — only Docker and Git. |
| AC-03 | The React frontend is accessible at `http://localhost:5173` (dev) or `http://localhost` (prod). |
| AC-04 | The FastAPI auto-generated docs are accessible at `http://localhost:8000/docs` (Swagger) and `/redoc`. |
| AC-05 | The React frontend can make authenticated API calls to FastAPI endpoints. |
| AC-06 | Database migrations run successfully via `docker-compose exec api alembic upgrade head`. |
| AC-07 | All lock files (`package-lock.json`, pinned `requirements.txt`) are committed to version control. |
| AC-08 | Code changes in `frontend/src`, `gateway/src`, and `api/app` trigger hot-reload without restarting containers. |
| AC-09 | `docker-compose down -v && docker-compose up --build` produces a fully clean, working environment. |

---

## 10. Open Questions

| # | Question | Status | Resolution |
|---|----------|--------|------------|
| Q1 | Should we use Poetry instead of pip + requirements.txt for the Python layer? | Open | |
| Q2 | Do we need the Node.js gateway from day one, or start with React → FastAPI direct? | Open | |
| Q3 | Should we adopt a monorepo tool (Nx, Turborepo) to manage frontend + gateway together? | Open | |
| Q4 | Do we need a production-grade orchestrator (Kubernetes, ECS) from the start, or is Docker Compose sufficient for early deployments? | Open | |

---

## Changelog

| Date | Change |
|------|--------|
| 2026-07-02 | Initial draft — React + Node.js + Python/FastAPI + MySQL stack |
