# Authentication & Login

## Metadata

| Field | Value |
|-------|-------|
| **Spec ID** | `core/auth-login` |
| **Title** | Authentication & Login |
| **Layer** | Core |
| **Status** | Draft |
| **Owner** | Platform Team |
| **Last Updated** | 2026-07-02 |
| **Depends On** | `platform/tech-stack`, `platform/auth-architecture`, `platform/database-conventions` |
| **Extended By** | `extensions/captcha-login`, `extensions/sso-saml` |

---

## 1. Overview

This spec defines how users register, log in, reset passwords, and manage their authentication sessions. It covers credential-based authentication, token lifecycle, and account security controls.

**In scope:**
- User registration (email + password)
- Login / logout
- Password reset via email
- JWT access + refresh token lifecycle
- Account lockout on failed attempts
- Session management

**Out of scope:**
- Role-based access control (see `core/user-management.md`)
- OAuth / SSO / SAML (see `extensions/sso-saml.md`)
- CAPTCHA (see `extensions/captcha-login.md`)
- User profile management (see `core/user-management.md`)

---

## 2. User Stories

| ID | Story | Priority |
|----|-------|----------|
| US-01 | As a new user, I want to register with my email and password, so that I can access the product. | Must |
| US-02 | As a registered user, I want to log in with my credentials, so that I receive an authenticated session. | Must |
| US-03 | As a logged-in user, I want to log out, so that my session is terminated securely. | Must |
| US-04 | As a user who forgot my password, I want to request a reset link, so that I can regain access. | Must |
| US-05 | As a user with a reset link, I want to set a new password, so that I can log in again. | Must |
| US-06 | As a security-conscious user, I want my account locked after repeated failed logins, so that brute-force attacks are prevented. | Should |
| US-07 | As a returning user, I want my session refreshed silently, so that I don't have to re-login frequently. | Should |

---

## 3. Data Model

### 3.1 Entity: `users`

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PK, auto-generated | |
| `email` | VARCHAR(255) | UNIQUE, NOT NULL | Normalized to lowercase |
| `password_hash` | VARCHAR(255) | NOT NULL | bcrypt, cost factor 12 |
| `is_active` | BOOLEAN | NOT NULL, DEFAULT true | Soft-disable accounts |
| `is_email_verified` | BOOLEAN | NOT NULL, DEFAULT false | Set true after verification |
| `failed_login_attempts` | INT | NOT NULL, DEFAULT 0 | Reset on successful login |
| `locked_until` | TIMESTAMP | NULLABLE | NULL = not locked |
| `last_login_at` | TIMESTAMP | NULLABLE | Updated on each login |
| `created_at` | TIMESTAMP | NOT NULL, auto-set | |
| `updated_at` | TIMESTAMP | NOT NULL, auto-updated | |

### 3.2 Entity: `refresh_tokens`

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PK, auto-generated | |
| `user_id` | UUID | FK → `users.id`, NOT NULL | CASCADE on delete |
| `token_hash` | VARCHAR(255) | UNIQUE, NOT NULL | SHA-256 hash of the token |
| `expires_at` | TIMESTAMP | NOT NULL | |
| `revoked_at` | TIMESTAMP | NULLABLE | NULL = active |
| `created_at` | TIMESTAMP | NOT NULL, auto-set | |

### 3.3 Entity: `password_reset_tokens`

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | UUID | PK, auto-generated | |
| `user_id` | UUID | FK → `users.id`, NOT NULL | CASCADE on delete |
| `token_hash` | VARCHAR(255) | UNIQUE, NOT NULL | SHA-256 hash of the token |
| `expires_at` | TIMESTAMP | NOT NULL | Default: 1 hour from creation |
| `used_at` | TIMESTAMP | NULLABLE | NULL = unused |
| `created_at` | TIMESTAMP | NOT NULL, auto-set | |

### 3.4 Indexes

| Index | Columns | Type | Rationale |
|-------|---------|------|-----------|
| `idx_users_email` | `email` | UNIQUE | Fast login lookup |
| `idx_refresh_tokens_user` | `user_id` | BTREE | List/revoke tokens per user |
| `idx_refresh_tokens_hash` | `token_hash` | UNIQUE | Token validation lookup |
| `idx_password_reset_hash` | `token_hash` | UNIQUE | Reset token validation |

---

## 4. API Contract

### 4.1 `POST /api/auth/register`

**Purpose:** Create a new user account.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "password_confirm": "SecurePass123!"
}
```

**Response (201):**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "is_email_verified": false,
  "created_at": "2026-07-02T12:00:00Z"
}
```

**Errors:**

| Status | Code | Description |
|--------|------|-------------|
| 400 | `VALIDATION_ERROR` | Missing fields, password too weak, passwords don't match |
| 409 | `EMAIL_ALREADY_EXISTS` | Email already registered |

**Side effects:**
- Sends verification email (async, non-blocking).

---

### 4.2 `POST /api/auth/login`

**Purpose:** Authenticate user and issue tokens.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGci...",
  "refresh_token": "dGhpcyBp...",
  "token_type": "Bearer",
  "expires_in": 900
}
```

**Errors:**

| Status | Code | Description |
|--------|------|-------------|
| 401 | `INVALID_CREDENTIALS` | Email or password incorrect |
| 403 | `ACCOUNT_LOCKED` | Too many failed attempts, locked until `locked_until` |
| 403 | `ACCOUNT_DISABLED` | `is_active` is false |
| 403 | `EMAIL_NOT_VERIFIED` | Email verification required |

**Flow:**
1. 🔌 **Pre-login hook** — run any registered pre-login extensions (CAPTCHA, IP check, etc.).
2. Validate email exists and account is not locked/disabled.
3. Verify password against `password_hash`.
4. Reset `failed_login_attempts` to 0.
5. Issue access token (short-lived) and refresh token (long-lived).
6. Update `last_login_at`.
7. 🔌 **Post-login hook** — run any registered post-login extensions (audit log, analytics, etc.).

> **Security note:** Response for invalid email and invalid password MUST be identical to prevent email enumeration.

---

### 4.3 `POST /api/auth/refresh`

**Purpose:** Exchange a valid refresh token for a new access token.

**Request:**
```json
{
  "refresh_token": "dGhpcyBp..."
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGci...",
  "refresh_token": "bmV3IHJl...",
  "token_type": "Bearer",
  "expires_in": 900
}
```

**Errors:**

| Status | Code | Description |
|--------|------|-------------|
| 401 | `INVALID_TOKEN` | Token expired, revoked, or malformed |

**Behavior:**
- Old refresh token is **revoked** (rotation).
- A new refresh token is issued alongside the new access token.
- If a revoked refresh token is reused → revoke ALL tokens for that user (compromise detection).

---

### 4.4 `POST /api/auth/logout`

**Purpose:** Revoke the current refresh token.

**Request:**
```json
{
  "refresh_token": "dGhpcyBp..."
}
```

**Response (204):** No content.

**Behavior:**
- Revokes the specified refresh token.
- Access token remains valid until expiry (stateless JWT).
- Client is responsible for discarding the access token.

---

### 4.5 `POST /api/auth/password-reset/request`

**Purpose:** Request a password reset email.

**Request:**
```json
{
  "email": "user@example.com"
}
```

**Response (200):**
```json
{
  "message": "If an account exists for this email, a reset link has been sent."
}
```

> **Security:** Always return 200 regardless of whether the email exists.

**Side effects:**
- If email exists → generate reset token, send email (async).
- Token expires in 1 hour (🔧 Configurable).
- Only one active reset token per user (previous ones invalidated).

---

### 4.6 `POST /api/auth/password-reset/confirm`

**Purpose:** Set a new password using a reset token.

**Request:**
```json
{
  "token": "reset-token-value",
  "password": "NewSecurePass456!",
  "password_confirm": "NewSecurePass456!"
}
```

**Response (200):**
```json
{
  "message": "Password has been reset successfully."
}
```

**Errors:**

| Status | Code | Description |
|--------|------|-------------|
| 400 | `VALIDATION_ERROR` | Password too weak, passwords don't match |
| 400 | `TOKEN_EXPIRED` | Reset token has expired |
| 400 | `TOKEN_USED` | Reset token was already used |
| 404 | `TOKEN_NOT_FOUND` | Invalid reset token |

**Side effects:**
- Revoke ALL existing refresh tokens for the user (force re-login everywhere).
- Mark reset token as used.

---

## 5. UI Behavior

### 5.1 Screen: Registration

**Layout:**
- Email input field
- Password input field (with strength indicator)
- Confirm password input field
- "Register" button
- Link to login page ("Already have an account?")

**Flow:**
1. User enters email + password + confirmation.
2. Client-side validation: email format, password strength, passwords match.
3. On submit → call `POST /api/auth/register`.
4. On success → redirect to "Check your email" confirmation screen.
5. On error → show inline error messages below the relevant fields.

**Validation rules (client-side, mirrored server-side):**
- Email: valid format, required.
- Password: minimum length (🔧), at least 1 uppercase, 1 lowercase, 1 digit, 1 special char.
- Confirm password: must match password field.

---

### 5.2 Screen: Login

**Layout:**
- Email input field
- Password input field
- "Log In" button
- "Forgot password?" link
- Link to registration page ("Don't have an account?")
- 🔌 **Pre-login extension slot** (e.g., CAPTCHA renders here when enabled)

**Flow:**
1. User enters email + password.
2. On submit → call `POST /api/auth/login`.
3. On success → store tokens, redirect to dashboard.
4. On `ACCOUNT_LOCKED` → show lockout message with time remaining.
5. On `INVALID_CREDENTIALS` → show generic error ("Invalid email or password").

---

### 5.3 Screen: Password Reset Request

**Layout:**
- Email input field
- "Send Reset Link" button
- Link back to login

**Flow:**
1. User enters email → call `POST /api/auth/password-reset/request`.
2. Always show "If an account exists, a reset link has been sent." (no email enumeration).
3. Redirect to login after 5 seconds or on user click.

---

### 5.4 Screen: Password Reset Confirm

**Layout:**
- New password input field (with strength indicator)
- Confirm password input field
- "Reset Password" button

**Flow:**
1. Page loads with reset token extracted from URL query parameter.
2. User enters new password + confirmation.
3. On submit → call `POST /api/auth/password-reset/confirm`.
4. On success → redirect to login with "Password reset successfully" toast.
5. On token error → show "Link expired or invalid" with option to request a new one.

---

## 6. Business Rules

| Rule | Description | Mutability |
|------|-------------|------------|
| BR-01 | Passwords MUST be hashed with bcrypt (cost factor 12) before storage. Never store plaintext. | 🔒 Sealed |
| BR-02 | Access tokens are stateless JWTs. Refresh tokens are stored server-side. | 🔒 Sealed |
| BR-03 | Refresh token rotation: issuing a new refresh token revokes the old one. | 🔒 Sealed |
| BR-04 | Reuse of a revoked refresh token triggers revocation of ALL user tokens. | 🔒 Sealed |
| BR-05 | Failed login responses MUST NOT reveal whether the email exists. | 🔒 Sealed |
| BR-06 | Account locks after N consecutive failed login attempts for M minutes. | 🔧 Configurable |
| BR-07 | Password must meet minimum length and complexity requirements. | 🔧 Configurable |
| BR-08 | Password reset tokens expire after a configurable duration. | 🔧 Configurable |
| BR-09 | Pre-login verification can be extended with additional checks. | 🔌 Extensible |
| BR-10 | Post-login actions can be extended with additional hooks. | 🔌 Extensible |

---

## 7. Mutability Decisions

### 🔒 Sealed (cannot be changed)

| Decision | Rationale |
|----------|-----------|
| Password hashing: bcrypt, cost 12 | Industry standard; switching algorithms requires full migration |
| Token model: stateless JWT access + server-side refresh | Core architecture; determines session management strategy |
| Refresh token rotation with reuse detection | Prevents token theft; fundamental security property |
| No email enumeration via login/reset endpoints | OWASP requirement; cannot be disabled per tenant |
| Email stored as lowercase | Prevents duplicate accounts; case-insensitive matching |

### 🔧 Configurable (tunable within bounds)

| Decision | Default | Range | Config Key |
|----------|---------|-------|------------|
| Access token TTL | 15 min | 5–60 min | `auth_access_token_ttl_minutes` |
| Refresh token TTL | 7 days | 1–30 days | `auth_refresh_token_ttl_days` |
| Password minimum length | 8 chars | 8–32 chars | `auth_password_min_length` |
| Failed attempts before lockout | 5 | 3–10 | `auth_max_failed_attempts` |
| Lockout duration | 15 min | 5–60 min | `auth_lockout_duration_minutes` |
| Password reset token TTL | 1 hour | 15 min–24 hours | `auth_reset_token_ttl_minutes` |
| Require email verification before login | true | true/false | `auth_require_email_verification` |

### 🔌 Extensible (can be extended, core preserved)

| Hook Point | What Can Be Added | What Cannot Change |
|-----------|-------------------|-------------------|
| Pre-login verification | CAPTCHA, IP allowlist, device fingerprint, geo-blocking | Core password verification MUST still execute after all pre-login checks pass |
| Post-login actions | Audit logging, analytics events, welcome notifications | Token issuance and response format cannot be altered |
| Pre-registration validation | Terms acceptance, invite-code check, domain allowlist | Core registration fields (email, password) and flow are fixed |
| Password policy | Additional complexity rules (no dictionary words, no reuse) | Minimum length floor of 8 cannot go below 8 |

---

## 8. Acceptance Criteria

| AC | Criteria | Covers |
|----|----------|--------|
| AC-01 | Given valid email + password, when I register, then my account is created and a verification email is sent. | US-01 |
| AC-02 | Given valid credentials, when I log in, then I receive an access token and refresh token. | US-02 |
| AC-03 | Given an invalid password, when I log in, then I see "Invalid email or password" (no email leak). | US-02, BR-05 |
| AC-04 | Given I am logged in, when I log out, then my refresh token is revoked. | US-03 |
| AC-05 | Given I forgot my password, when I request a reset, then I receive an email with a reset link (if account exists). | US-04 |
| AC-06 | Given a valid reset token, when I submit a new password, then my password is updated and all sessions are revoked. | US-05 |
| AC-07 | Given an expired reset token, when I try to use it, then I see "Link expired" with an option to request a new one. | US-05 |
| AC-08 | Given 5 consecutive failed logins, when I try again, then my account is locked for 15 minutes. | US-06, BR-06 |
| AC-09 | Given a valid refresh token, when I call `/refresh`, then I get a new access + refresh token pair and the old refresh token is revoked. | US-07, BR-03 |
| AC-10 | Given a revoked refresh token, when it is reused, then ALL tokens for that user are revoked. | BR-04 |

---

## 9. Non-Functional Requirements

| Requirement | Target | Notes |
|-------------|--------|-------|
| Login response time | < 300ms p95 | bcrypt is intentionally slow; 300ms budget accounts for this |
| Registration response time | < 500ms p95 | Email sending is async and excluded from this target |
| Token refresh response time | < 100ms p95 | Lightweight DB lookup + JWT signing |
| Availability | 99.9% | Auth is a critical path — no degraded mode |
| Security | OWASP Top 10 compliant | Covers injection, broken auth, XSS, CSRF |
| Rate limiting | 10 login attempts/min per IP | Prevents brute force before account lockout kicks in |
| Accessibility | WCAG 2.1 AA | All forms keyboard-navigable, screen-reader compatible |

---

## 10. Open Questions

| # | Question | Status | Resolution |
|---|----------|--------|------------|
| Q1 | Should we support "Remember me" (extended refresh token TTL)? | Open | |
| Q2 | Should email verification be blocking (can't login until verified) or non-blocking (can login, but limited access)? | Open | Currently set as configurable (`auth_require_email_verification`) |
| Q3 | Do we need rate limiting at the API gateway level in addition to application-level lockout? | Open | |

---

## Changelog

| Date | Change |
|------|--------|
| 2026-07-02 | Initial draft |
