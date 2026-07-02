# Spec Template

> Copy this template when creating a new spec. Delete any sections that don't apply.
> Place the finished spec in the correct layer directory:
> - `specs/platform/` — for tech stack, conventions, infrastructure
> - `specs/core/` — for standard product features
> - `specs/extensions/` — for optional/tenant-specific additions

---

## Metadata

| Field | Value |
|-------|-------|
| **Spec ID** | `<layer>/<filename>` (e.g., `core/auth-login`) |
| **Title** | Human-readable feature name |
| **Layer** | Platform · Core · Extension |
| **Status** | Draft · In Review · Approved · Implemented · Deprecated |
| **Owner** | Team or individual responsible |
| **Last Updated** | YYYY-MM-DD |
| **Depends On** | List of specs this depends on (e.g., `platform/auth-architecture`) |
| **Extended By** | List of extension specs that extend this (fill in as they're created) |

> **Extension-only fields** (include only for Layer 3 specs):
>
> | Field | Value |
> |-------|-------|
> | **Extends** | `core/<parent-spec>.md` |
> | **Feature Flag** | `enable_<feature_name>` |
> | **Requested By** | Anonymized customer context or internal initiative |
> | **Graduation Criteria** | When this should move to core |

---

## 1. Overview

A brief description of what this spec covers and why it exists. 2–4 sentences max.

**In scope:**
- What this spec governs

**Out of scope:**
- What this spec intentionally does NOT cover (and where to find it instead)

---

## 2. User Stories

> Format: As a [role], I want [action], so that [outcome].

| ID | Story | Priority |
|----|-------|----------|
| US-01 | As a [role], I want to [action], so that [outcome]. | Must |
| US-02 | ... | Should |
| US-03 | ... | Could |

---

## 3. Data Model

Define the entities, fields, types, and constraints relevant to this feature.

### 3.1 Entity: `<EntityName>`

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PK, auto-generated | |
| `created_at` | Timestamp | NOT NULL, auto-set | |
| `updated_at` | Timestamp | NOT NULL, auto-updated | |
| ... | ... | ... | ... |

### 3.2 Relationships

- `EntityA` → `EntityB` (one-to-many via `entity_a_id` FK)

### 3.3 Indexes

| Index | Columns | Type | Rationale |
|-------|---------|------|-----------|
| ... | ... | UNIQUE / BTREE / FULLTEXT | ... |

---

## 4. API Contract

Define the endpoints, methods, request/response shapes, and error codes.

### 4.1 `POST /api/<resource>`

**Purpose:** Brief description.

**Request:**
```json
{
  "field": "value"
}
```

**Response (201):**
```json
{
  "id": "uuid",
  "field": "value",
  "created_at": "ISO-8601"
}
```

**Errors:**

| Status | Code | Description |
|--------|------|-------------|
| 400 | `VALIDATION_ERROR` | Request body failed validation |
| 401 | `UNAUTHORIZED` | Missing or invalid auth token |
| 409 | `CONFLICT` | Resource already exists |

> Repeat for each endpoint (GET, PUT, PATCH, DELETE, etc.)

---

## 5. UI Behavior

Describe screens, user flows, and interaction rules. Use numbered steps for flows.

### 5.1 Screen: `<ScreenName>`

**Layout:**
- Description of key UI elements and their arrangement.

**Flow:**
1. User does X → system shows Y.
2. If validation fails → show inline error Z.
3. On success → redirect to / show confirmation.

**States:**
| State | Behavior |
|-------|----------|
| Loading | Show skeleton / spinner |
| Empty | Show empty-state message |
| Error | Show error banner with retry option |
| Success | Show confirmation / redirect |

---

## 6. Business Rules

Numbered list of rules that govern the feature's behavior. These are the "laws" that code must enforce.

| Rule | Description | Mutability |
|------|-------------|------------|
| BR-01 | Description of the rule | 🔒 Sealed / 🔧 Configurable / 🔌 Extensible |
| BR-02 | ... | ... |

---

## 7. Mutability Decisions

Explicitly tag every significant decision using the framework's mutability model.

### 🔒 Sealed (cannot be changed)

| Decision | Rationale |
|----------|-----------|
| ... | ... |

### 🔧 Configurable (tunable within bounds)

| Decision | Default | Range | Config Key |
|----------|---------|-------|------------|
| ... | ... | ... | `config_key` |

### 🔌 Extensible (can be extended, core preserved)

| Hook Point | What Can Be Added | What Cannot Change |
|-----------|-------------------|-------------------|
| ... | ... | ... |

---

## 8. Acceptance Criteria

Testable conditions that define "done" for this spec.

| AC | Criteria | Covers |
|----|----------|--------|
| AC-01 | Given [precondition], when [action], then [result]. | US-01 |
| AC-02 | ... | US-02 |

---

## 9. Non-Functional Requirements

| Requirement | Target | Notes |
|-------------|--------|-------|
| Response time | < 200ms p95 | For primary API endpoints |
| Availability | 99.9% | Standard SLA |
| Security | OWASP Top 10 compliant | ... |
| Accessibility | WCAG 2.1 AA | ... |

---

## 10. Open Questions

> Track unresolved decisions here. Move to the relevant section once resolved.

| # | Question | Status | Resolution |
|---|----------|--------|------------|
| Q1 | ... | Open / Resolved | ... |

---

## Changelog

| Date | Change |
|------|--------|
| YYYY-MM-DD | Initial draft |
