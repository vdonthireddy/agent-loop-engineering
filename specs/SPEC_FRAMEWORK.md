# SaaS Spec Framework

A layered specification system for governing how any SaaS product is built, what features exist, and how customers can extend it.

> **Status:** Draft — evolving through discussion.
> **Last updated:** 2026-07-02

---

## 1. Why Specs?

As a SaaS product matures beyond its initial build, teams need a structured way to:

1. **Define what the product is** — so any developer or agent can implement features correctly.
2. **Separate platform decisions from product features** — tech stack choices shouldn't be mixed with UI behavior.
3. **Support multi-tenant customization** — without forking the codebase for each customer.
4. **Enable agentic development** — specs become the contract that an agent loop validates against.

This framework is **product-agnostic**. Adapt the examples to your domain — the structure and rules apply to any SaaS application.

---

## 2. The Three Layers

Specs are organized into three layers, each with a distinct purpose and audience.

### Layer 1: Platform (`specs/platform/`)

**What it defines:** Technical foundations, architectural decisions, coding conventions, and infrastructure choices that apply globally to the entire product.

**Audience:** Engineers, DevOps, agents implementing any feature.

**Examples:**
- Technology stack (database, backend framework, frontend framework)
- API design conventions (REST/GraphQL, error format, pagination)
- Authentication architecture (session/token flow, token lifecycle)
- Database conventions (naming, migration strategy, multi-tenancy approach)
- UI design system (component library, theming, accessibility standards)
- Deployment & infrastructure (CI/CD, hosting, environments)
- Observability (logging, monitoring, alerting conventions)

**Key property:** Most decisions in platform specs are **🔒 Sealed** — they represent commitments that cannot be overridden by features or customer requests.

---

### Layer 2: Core Features (`specs/core/`)

**What it defines:** The standard product functionality that every tenant gets out of the box. These are the features that define the product's identity.

**Audience:** Product managers, engineers, agents building standard features.

**Examples** (adapt to your domain):
- Authentication & authorization (registration, login, password reset, RBAC)
- User/account management (profiles, teams, invitations)
- Primary domain entity CRUD (the core "thing" your product manages)
- Dashboard & analytics (charts, metrics, activity feed)
- Notifications (email, in-app, webhook)
- Search & filtering (full-text, faceted, saved views)
- AI-powered features (suggestions, generation, summarization)
- Real-time collaboration (WebSocket sync, presence)
- Import/export (CSV, JSON, PDF, API)
- Billing & subscription management (plans, usage metering, invoices)

**Key property:** Core specs define the baseline product. They may contain **🔧 Configurable** parameters (e.g., token expiry) and **🔌 Extensible** hooks (e.g., pre-login steps) that Layer 3 extensions can use.

---

### Layer 3: Extensions (`specs/extensions/`)

**What it defines:** Optional, tenant-specific, or experimental features that extend or customize core behavior. These are modular additions — not forks.

**Audience:** Engineers working on customer-specific requests, product managers evaluating feature requests.

**Why "extensions" and not "customer-specific":**
- We don't name specs after specific customers (no `acme-corp-captcha.md`).
- Extensions are **modular additions**, not forks of core behavior.
- Extensions have a natural **graduation path** — when enough tenants need it, it moves to core.

**Examples** (adapt to your domain):
- CAPTCHA on login (extends: `core/auth-login.md`)
- SSO/SAML integration (extends: `core/auth-login.md`)
- Custom branding/white-labeling (extends: `platform/ui-design-system.md`)
- Advanced audit logging (extends: `core/user-management.md`)
- Custom webhook integrations (extends: `core/notifications.md`)
- Industry-specific entity types (extends: the relevant core entity spec)

**Key property:** Every extension spec **must reference the parent spec it extends** and must not violate any 🔒 Sealed decisions.

---

## 3. Mutability Model

Not all decisions are created equal. Some are permanent commitments, others are tunable, and others are designed to be extended. This applies to individual decisions **within any layer**, not to entire layers.

### 🔒 Sealed

**Cannot be changed or overridden. Period.**

These are architectural commitments. Changing them would require a fundamental redesign.

| Example Decision | Spec |
|----------|------|
| Primary database engine: `<your choice>` | `platform/tech-stack.md` |
| Backend language: `<your choice>` | `platform/tech-stack.md` |
| Backend framework: `<your choice>` | `platform/tech-stack.md` |
| Frontend framework: `<your choice>` | `platform/tech-stack.md` |
| Auth mechanism: `<your choice>` | `platform/auth-architecture.md` |
| API format: `<your choice>` | `platform/api-conventions.md` |
| ORM / data access layer: `<your choice>` | `platform/database-conventions.md` |

> **Rule for agents:** An agent must NEVER generate code that contradicts a 🔒 Sealed decision.

---

### 🔧 Configurable

**Can be tuned within defined bounds, but not replaced.**

These have sensible defaults that tenants can adjust via configuration (e.g., a `tenant_config` table, environment variables, or feature flags).

| Example Decision | Default | Allowed Range | Config Key |
|----------|---------|--------------|------------|
| Auth token TTL | 15 min | 5–60 min | `auth_token_ttl_minutes` |
| Password minimum length | 8 chars | 8–32 chars | `auth_password_min_length` |
| Max items per list page | 25 | 10–100 | `pagination_default_page_size` |
| Max records per import batch | 1,000 | 100–10,000 | `import_max_batch_size` |
| File upload size limit | 10 MB | 1–100 MB | `upload_max_file_size_mb` |

> **Rule for agents:** An agent can adjust these values but ONLY within the stated bounds.

---

### 🔌 Extensible

**Can be extended with new behavior, but core behavior must be preserved.**

These are designed hook points where extensions can add functionality without modifying or bypassing the core logic.

| Example Hook Point | What Can Be Added | What Cannot Be Changed |
|-----------|-------------------|----------------------|
| Pre-login verification | CAPTCHA, IP allowlist, device fingerprint | Core credential verification must still execute |
| Entity fields | Custom fields alongside standard ones | Standard fields (name, email, created_at, etc.) cannot be removed |
| Notification channels | New channels (Slack, SMS, PagerDuty) | Existing email/in-app notifications remain unchanged |
| Export formats | New formats (XLSX, PPT, XML) | Existing built-in exports remain unchanged |
| Webhook events | New event types | Core event schema and delivery guarantees are fixed |

> **Rule for agents:** An agent can ADD new behavior at extensible hooks but must PRESERVE all existing core behavior.

---

## 4. Layer Relationships

```
┌─────────────────────────────────────────────────────┐
│           Layer 1: Platform                          │
│   (tech stack, conventions, architecture)            │
│   Mostly 🔒 Sealed                                   │
│                                                       │
│   ┌─────────────────────────────────────────────┐    │
│   │       Layer 2: Core Features                 │    │
│   │   (auth, entities, dashboard, billing)       │    │
│   │   Mix of 🔒 🔧 🔌                            │    │
│   │                                               │    │
│   │   ┌─────────────────────────────────────┐    │    │
│   │   │    Layer 3: Extensions               │    │    │
│   │   │  (CAPTCHA, SSO, branding, webhooks)  │    │    │
│   │   │  Uses 🔧 and 🔌 only                 │    │    │
│   │   └─────────────────────────────────────┘    │    │
│   └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

**Inheritance rules:**
- Layer 3 inherits ALL constraints from Layer 2 and Layer 1.
- Layer 3 can only use 🔧 Configurable parameters and 🔌 Extensible hooks.
- Layer 3 can NEVER override 🔒 Sealed decisions from any layer.
- Layer 2 inherits ALL constraints from Layer 1.

---

## 5. Extension Lifecycle: Graduation Path

Extensions are not permanent. They follow a lifecycle:

```
Requested → Specced → Implemented → Evaluated → Graduated (or Retired)
```

### Graduation Criteria

An extension should be promoted to a **core feature** (moved from `extensions/` to `core/`) when:

- ✅ Requested by **3 or more tenants**
- ✅ No tenant-specific business logic remains (fully generalized)
- ✅ Can be controlled via a **configuration toggle** (not hard-coded)
- ✅ Has been **production-stable** for at least one release cycle

### Retirement Criteria

An extension should be **retired** (archived or removed) when:

- The requesting tenant churns and no other tenant uses it
- A better core feature supersedes it
- It creates unacceptable maintenance burden

---

## 6. Extension Spec Required Metadata

Every extension spec must include this header block:

```markdown
## Extension Metadata
- **Extends:** core/<parent-spec>.md
- **Feature Flag:** `enable_<feature_name>`
- **Mutability:** 🔌 Extensible (describe the hook used)
- **Requested By:** [Anonymized customer context or internal initiative]
- **Graduation Criteria:** 3+ tenants request → promote to core with toggle
- **Status:** Draft | Approved | Implemented | Graduated | Retired
```

---

## 7. Proposed Directory Structure

```
specs/
├── SPEC_FRAMEWORK.md                   # This document
├── SPEC_TEMPLATE.md                    # Template for writing new specs
│
├── platform/                           # Layer 1: Technical Foundation
│   ├── tech-stack.md                   # Languages, frameworks, versions
│   ├── api-conventions.md              # API patterns, error format, pagination
│   ├── auth-architecture.md            # Auth flow, RBAC model, token lifecycle
│   ├── database-conventions.md         # Naming, migrations, multi-tenancy
│   ├── ui-design-system.md             # Components, theming, accessibility
│   └── infrastructure.md              # Deployment, CI/CD, environments
│
├── core/                               # Layer 2: Standard Product Features
│   ├── auth-login.md                   # Registration, login, password reset
│   ├── user-management.md              # Profiles, teams, roles, invitations
│   ├── <domain-entity>.md              # Your product's primary entity CRUD
│   ├── dashboard.md                    # Charts, metrics, activity feed
│   ├── notifications.md               # Email, in-app, webhooks
│   ├── search.md                       # Full-text, faceted, saved views
│   ├── ai-features.md                 # AI-powered capabilities
│   ├── collaboration.md               # Real-time sync, presence
│   ├── export-import.md               # CSV/JSON/PDF import and export
│   └── billing.md                     # Plans, usage, invoices
│
└── extensions/                         # Layer 3: Tenant-Specific / Optional
    ├── _template.md                    # Extension template (with required metadata)
    ├── captcha-login.md                # Extends: core/auth-login.md
    ├── sso-saml.md                     # Extends: core/auth-login.md
    └── custom-branding.md              # Extends: platform/ui-design-system.md
```

> **Note:** Replace `<domain-entity>.md` with your product's core entities — e.g., `project-management.md`, `lead-management.md`, `inventory.md`, `order-management.md`, etc.

---

## 8. How to Adopt This Framework

### Step 1: Fill in Platform Specs

Start with `platform/tech-stack.md`. Document every 🔒 Sealed decision your team has already made. These are facts, not aspirations.

### Step 2: Enumerate Core Features

List every feature your product ships to all tenants. Create one spec per feature in `core/`. Mark each decision within as 🔒, 🔧, or 🔌.

### Step 3: Identify Existing Customizations

Audit your codebase for tenant-specific code, feature flags, or one-off branches. Each one is a candidate for an extension spec in `extensions/`.

### Step 4: Enforce via Agent Loops

If using agentic development, configure your agent loop to:
- Load relevant specs before generating code.
- Validate output against 🔒 Sealed decisions.
- Respect 🔧 bounds for configurable parameters.
- Only extend at designated 🔌 hook points.

---

## 9. Open Questions

> **Q1:** How do we handle an extension that needs to modify multiple core specs? Should it reference multiple parents, or split into separate extension specs per parent?

> **Q2:** Should configurable parameters (🔧) live in the spec, in a separate config schema file, or both?

> **Q3:** Do we need a formal review/approval process for graduating an extension to core? Or is it a team judgment call?

> **Q4:** Should the codebase have a `tenant_config` table from the start, or should it be added when the first extension is actually implemented?

> **Q5:** How should specs handle versioning? When a core spec changes, how do we track backward compatibility for existing extensions?

---

## Changelog

| Date | Change |
|------|--------|
| 2026-07-02 | Generalized from product-specific to SaaS-agnostic framework |
| 2026-07-02 | Initial draft — three-layer model with mutability levels |
