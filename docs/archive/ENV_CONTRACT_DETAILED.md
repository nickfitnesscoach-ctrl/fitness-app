# ENV Contract - EatFit24

**Version:** 1.0
**Last Updated:** 2025-12-21

This document defines the source of truth for all environment variables in the EatFit24 project.

---

## Variable Groups

### 1. Compose-Level Variables

**Location:** `/.env`
**Purpose:** Docker Compose interpolation, non-sensitive configuration

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `COMPOSE_PROJECT_NAME` | string | No | eatfit24 | Docker project prefix |
| `POSTGRES_DB` | string | Yes | - | Database name |
| `POSTGRES_HOST` | string | No | db | Database host (service name) |
| `POSTGRES_PORT` | int | No | 5432 | Database port |
| `ALLOWED_HOSTS` | csv | Yes | - | Django allowed hosts |
| `CORS_ALLOWED_ORIGINS` | csv | Yes | - | CORS allowed origins (HTTPS only in prod) |
| `WEB_APP_URL` | url | Yes | - | Telegram Mini App URL |
| `TRAINER_PANEL_BASE_URL` | url | Yes | - | Trainer panel base URL |
| `DJANGO_API_URL` | url | No | http://backend:8000/api/v1 | Internal API URL for bot |
| `YOOKASSA_RETURN_URL` | url | Yes | - | Payment return URL |
| `DEBUG` | bool | No | False | Django debug mode |
| `DEBUG_MODE_ENABLED` | bool | No | False | Browser debug auth |
| `AI_ASYNC_ENABLED` | bool | No | True | Async AI processing |
| `BILLING_RECURRING_ENABLED` | bool | No | false | YooKassa recurring |
| `YOOKASSA_MODE` | enum | Yes | test | test or prod |
| `TELEGRAM_ADMINS` | csv | Yes | - | **Primary admin variable** - Comma-separated Telegram user IDs with admin privileges (used by backend AND bot) |
| `BOT_ADMIN_ID` | int | No | - | **Legacy** - Superseded by TELEGRAM_ADMINS, kept for backward compatibility |
| `ADMIN_IDS` | csv | No | - | **Legacy** - Superseded by TELEGRAM_ADMINS, kept for backward compatibility |
| `WEBHOOK_TRUST_XFF` | bool | No | false | Trust X-Forwarded-For |
| `WEBHOOK_TRUSTED_PROXIES` | csv | No | 127.0.0.1 | Trusted proxy IPs |

---

### 2. Backend Runtime Secrets

**Location:** `/env/backend.env` (NOT in git)
**Purpose:** Sensitive credentials for backend, worker, beat containers

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| `POSTGRES_USER` | string | Yes | Database username |
| `POSTGRES_PASSWORD` | string | Yes | Database password |
| `SECRET_KEY` | string | Yes | Django secret key (64 hex chars) |
| `TELEGRAM_BOT_TOKEN` | string | Yes | Telegram bot token |
| `TELEGRAM_BOT_API_SECRET` | string | Yes | Bot API authentication secret |
| `OPENROUTER_API_KEY` | string | Yes | OpenRouter API key |
| `SWAGGER_AUTH_USERNAME` | string | No | Swagger basic auth username |
| `SWAGGER_AUTH_PASSWORD` | string | No | Swagger basic auth password |
| `YOOKASSA_SHOP_ID_TEST` | string | Yes* | YooKassa test shop ID |
| `YOOKASSA_API_KEY_TEST` | string | Yes* | YooKassa test secret key |
| `YOOKASSA_SHOP_ID_PROD` | string | Yes* | YooKassa production shop ID |
| `YOOKASSA_API_KEY_PROD` | string | Yes* | YooKassa production secret key |
| `AI_PROXY_URL` | url | No | AI Proxy service URL |
| `AI_PROXY_SECRET` | string | No | AI Proxy authentication secret |

*Required based on YOOKASSA_MODE

---

### 3. Worker Runtime Variables

**Location:** Inherits from backend.env + compose
**Purpose:** Celery worker specific config

Worker uses same secrets as backend plus:

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `CELERY_BROKER_URL` | url | Yes | redis://redis:6379/0 | Redis broker |
| `CELERY_RESULT_BACKEND` | url | Yes | redis://redis:6379/0 | Redis results |
| `REDIS_URL` | url | No | redis://redis:6379/1 | Cache Redis |

---

### 4. Frontend Public Config (VITE_*)

> [!CAUTION]
> **`.env.production` MUST NOT EXIST and MUST NOT be used.**
> Frontend VITE variables are passed via Docker build args ONLY.

**Location (Production):** `docker-compose.yml` → `build.args` → Dockerfile `ARG`/`ENV`
**Location (Development):** `/frontend/.env.development` (local only, NOT in git)
**Purpose:** Build-time variables embedded into JavaScript bundle during `npm run build`

#### Production Build Flow

```
docker-compose.yml (build.args)
    ↓
Dockerfile (ARG → ENV)
    ↓
npm run build (Vite reads ENV)
    ↓
JavaScript bundle (values hardcoded)
```

#### Variables

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `VITE_API_URL` | path | No | /api/v1 | API base path (relative) |
| `VITE_TELEGRAM_BOT_NAME` | string | No | EatFit24_bot | Bot username for links |
| `VITE_TRAINER_INVITE_LINK` | url | No | https://t.me/EatFit24_bot | Trainer invite URL |

**Development only (never in production):**

| Variable | Type | Description |
|----------|------|-------------|
| `VITE_MOCK_TELEGRAM` | 0/1 | Mock Telegram WebApp SDK |
| `VITE_SKIP_TG_AUTH` | bool | Skip auth check in browser |

#### Critical Security Rules

1. **ALL `VITE_*` variables are PUBLIC** - they are embedded in the JavaScript bundle and visible to any user via browser DevTools
2. **NEVER use `VITE_` prefix for secrets** - no API keys, tokens, passwords, or any sensitive data
3. **`.env.production` must NOT exist** - using it creates a Docker image security risk (file embedded in layers)
4. **Production values are in `docker-compose.yml`** - defined once, used during build
5. **Fallback values in `vite.config.js`** - ensures build succeeds even if args not provided

#### Example: What NOT to do

```env
# ❌ WRONG - This file should NOT exist
# frontend/.env.production
VITE_API_URL=/api/v1
VITE_SECRET_KEY=abc123  # ❌ CRITICAL ERROR - secret in frontend!
```

#### Example: Correct Configuration

```yaml
# ✅ CORRECT - docker-compose.yml
services:
  frontend:
    build:
      args:
        - VITE_API_URL=/api/v1
        - VITE_TELEGRAM_BOT_NAME=EatFit24_bot
```

```dockerfile
# ✅ CORRECT - Dockerfile
ARG VITE_API_URL=/api/v1
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build
```

> [!IMPORTANT]
> Any variable accessible in frontend runtime is considered **public by definition**.
> If data must remain secret, it belongs in the backend, not the frontend.

---

### 5. Bot Runtime Secrets

> [!NOTE]
> **Updated 2025-12-24:** Bot is now **API-only**. 
> Direct database access has been removed. All data operations go through Django API.

**Location:** `docker-compose.yml` environment section
**Purpose:** Telegram bot runtime secrets and configuration

#### Current State (API-only architecture)

The bot communicates with Django backend via HTTP API (`BackendAPIClient`):

```
┌───────────┐    X-Bot-Secret    ┌───────────┐    ┌──────────┐
│    Bot    │ ─────────────────▶ │  Django   │───▶│ Postgres │
└───────────┘    (httpx)         │  Backend  │    └──────────┘
                                 └───────────┘
```

#### Required Variables

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Secret | ✅ | Telegram bot API token |
| `TELEGRAM_BOT_API_SECRET` | Secret | ✅ | Shared secret for X-Bot-Secret header |
| `OPENROUTER_API_KEY` | Secret | ✅ | AI API key for plan generation |
| `DJANGO_API_URL` | Config | ✅ | Backend API URL (e.g., `http://backend:8000/api/v1`) |
| `WEB_APP_URL` | Config | ⚠️ | Telegram Mini App URL |
| `TRAINER_PANEL_BASE_URL` | Config | ⚠️ | Trainer panel base URL |
| `BOT_ADMIN_ID` | Config | ⚠️ | Primary admin Telegram ID |
| `TELEGRAM_ADMINS` | Config | ⚠️ | Admin Telegram IDs (csv) |
| `ENVIRONMENT` | Config | ⚠️ | `production` or `development` |

#### Removed Variables (no longer needed)

| Variable | Status | Reason |
|----------|--------|--------|
| `DB_HOST` | ❌ Removed | Bot uses Django API, not direct DB |
| `DB_PORT` | ❌ Removed | Bot uses Django API, not direct DB |
| `DB_NAME` | ❌ Removed | Bot uses Django API, not direct DB |
| `DB_USER` | ❌ Removed | Bot uses Django API, not direct DB |
| `DB_PASSWORD` | ❌ Removed | Bot uses Django API, not direct DB |

#### docker-compose.yml Example

```yaml
bot:
  environment:
    - ENVIRONMENT=production
    - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
    - TELEGRAM_BOT_API_SECRET=${TELEGRAM_BOT_API_SECRET}
    - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
    - DJANGO_API_URL=http://backend:8000/api/v1
    - WEB_APP_URL=${WEB_APP_URL}
    - BOT_ADMIN_ID=${BOT_ADMIN_ID}
    - TELEGRAM_ADMINS=${TELEGRAM_ADMINS}
  depends_on:
    backend:
      condition: service_healthy  # Bot depends on backend, not db
```

#### Principle: Least Privilege

Bot should ONLY receive secrets it actually needs:
- ✅ Bot needs: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_API_SECRET`, `OPENROUTER_API_KEY`
- ✅ Bot needs: `DJANGO_API_URL` (backend connection)
- ❌ Bot does NOT need: `DB_*`, `YOOKASSA_*`, `SECRET_KEY`, `SWAGGER_*`

---

## Admin IDs - Single Source of Truth

> [!WARNING]
> **Use ONLY `TELEGRAM_ADMINS`** - Other admin variables are legacy and should not be used for new code.

### Current State

Three variables exist for historical reasons:
- `TELEGRAM_ADMINS` (csv) - **PRIMARY, USE THIS**
- `BOT_ADMIN_ID` (int) - Legacy, kept for compatibility
- `ADMIN_IDS` (csv) - Legacy, kept for compatibility

### Format

```env
# ✅ CORRECT - Use this
TELEGRAM_ADMINS=310151740,987654321,123456789

# ❌ DEPRECATED - Avoid using these
BOT_ADMIN_ID=310151740
ADMIN_IDS=310151740,987654321
```

### Who Uses What

| Service | Variable Used | Purpose |
|---------|---------------|---------|
| Backend | `TELEGRAM_ADMINS` | Admin permission checks |
| Bot | `TELEGRAM_ADMINS` | Admin commands |
| Bot | `BOT_ADMIN_ID` | Legacy fallback |
| Bot | `ADMIN_IDS` | Legacy fallback |

### Migration Plan

1. **Immediate:** Always set `TELEGRAM_ADMINS` in `.env`
2. **Short-term:** Update bot code to use only `TELEGRAM_ADMINS`
3. **Long-term:** Remove `BOT_ADMIN_ID` and `ADMIN_IDS` from codebase

---

## 🔒 Security Invariants (Non-Negotiable)

> [!CAUTION]
> **These are INVARIANTS, not recommendations.**
> Violation of any rule below is a security vulnerability.

### Production Environment Rules

| Rule | Value | Enforcement |
|------|-------|-------------|
| `DEBUG` | **MUST be `False`** | CI check, startup validation |
| `DEBUG_MODE_ENABLED` | **MUST be `False`** | CI check, startup validation |
| `ENVIRONMENT` | **MUST be `production`** | Startup log |

**Rationale:**
- `DEBUG=True` exposes sensitive data in error pages (SQL queries, internal paths, settings)
- `DEBUG_MODE_ENABLED=True` allows auth bypass via `X-Debug-Mode` header

### Secrets Rules

| Pattern | Rule | Example Violation |
|---------|------|-------------------|
| `*_SECRET` | **NO defaults** | `SECRET_KEY=changeme` ❌ |
| `*_TOKEN` | **NO defaults** | `TELEGRAM_BOT_TOKEN=test` ❌ |
| `*_API_KEY` | **NO defaults** | `OPENROUTER_API_KEY=sk-xxx` ❌ |
| `*_PASSWORD` | **NO defaults** | `POSTGRES_PASSWORD=postgres` ❌ |

**Forbidden values:**
- `changeme`, `change_me`, `CHANGEME`
- `test`, `testing`, `dev`, `development`
- `secret`, `password`, `token`
- `123`, `123456`, `password123`
- Empty string

**Generation:**
```bash
# ✅ CORRECT - Generate strong secrets
openssl rand -hex 32
# Output: your-randomly-generated-hex-secret-here
```

### CORS Rules

| Environment | Allowed Value | Forbidden Value |
|-------------|---------------|-----------------|
| Production | Explicit origins: `https://eatfit24.ru` | `*` (wildcard) ❌ |
| Development | `http://localhost:3000,http://localhost:5173` | `*` (wildcard) ❌ |

**Rationale:** Wildcard CORS (`*`) allows any malicious website to make authenticated requests on behalf of users.

### Admin Lists Rules

| Rule | Example |
|------|---------|
| **NO auto-expansion** | ❌ `TELEGRAM_ADMINS=${TELEGRAM_ADMINS},999999999` |
| **NO hardcoded test IDs** | ❌ `TELEGRAM_ADMINS=310151740,999999999` |
| **Explicit only** | ✅ `TELEGRAM_ADMINS=310151740` |

**Rationale:** Automatic expansion of admin lists in `docker-compose.yml` creates backdoors (e.g., debug user 999999999 gaining admin access).

### Frontend Security Rules

| Rule | Enforcement |
|------|-------------|
| **NO `.env.production` file** | Must be in `.gitignore`, build fails if present |
| **NO secrets in `VITE_*`** | Code review, grep check: `grep -r "VITE_.*SECRET"` |
| **Build args only** | Production build via `docker-compose.yml` build.args |

### Enforcement

#### CI/CD Checks (MUST implement)

```bash
# Fail build if violations found
[ "$DEBUG" = "True" ] && echo "ERROR: DEBUG=True in prod" && exit 1
[ "$DEBUG_MODE_ENABLED" = "True" ] && echo "ERROR: DEBUG_MODE_ENABLED=True" && exit 1
grep -E "changeme|test|123456" .env && echo "ERROR: Weak secrets" && exit 1
grep -E "VITE_.*SECRET" frontend/ && echo "ERROR: Secret in frontend" && exit 1
```

#### Startup Validation (Backend)

```python
# config/settings/production.py
if DEBUG:
    raise ImproperlyConfigured("DEBUG must be False in production")
if DEBUG_MODE_ENABLED:
    raise ImproperlyConfigured("DEBUG_MODE_ENABLED must be False in production")
if SECRET_KEY in ["changeme", "test"]:
    raise ImproperlyConfigured("SECRET_KEY must be a strong random value")
```

---

## Rules

### Rule A: Frontend Security

- All `VITE_*` variables are **PUBLIC** (embedded in JS bundle)
- **NEVER** put secrets in frontend env files
- **NEVER** use `VITE_` prefix for: API keys, tokens, passwords, secrets
- **NEVER** create `/frontend/.env.production` file
- Production VITE values **ONLY** via `docker-compose.yml` build args

### Rule B: Backend/Worker Secrets

- Secrets must be in `env/backend.env` or Docker secrets
- **NEVER** commit secrets to git
- **NEVER** use default/placeholder values in production
- Generate secrets with: `openssl rand -hex 32`
- Validate secrets at startup (fail fast if weak)

### Rule C: Compose-Level .env

**Allowed:**
- Domain names, URLs
- Feature flags (boolean)
- Non-sensitive IDs
- Service names

**NOT Allowed:**
- Passwords
- API keys
- Tokens
- Private keys

### Rule D: Single Source of Truth

Each variable has ONE source:

| Source | Variables |
|--------|-----------|
| `/.env` | Compose interpolation, non-secrets |
| `/env/backend.env` | Backend secrets |
| `docker-compose.yml` build.args | Frontend VITE variables |
| `docker-compose.yml` environment | Runtime config (ports, URLs) |

**Derived variables** (calculated from others) are **FORBIDDEN** for security-critical values (admins, debug flags).

---

## Validation

### Required Variables Check

```bash
# Check required compose variables
required_vars=(
  POSTGRES_DB
  POSTGRES_PASSWORD
  SECRET_KEY
  ALLOWED_HOSTS
  CORS_ALLOWED_ORIGINS
  TELEGRAM_BOT_TOKEN
  YOOKASSA_MODE
)

for var in "${required_vars[@]}"; do
  if [ -z "${!var}" ]; then
    echo "ERROR: $var is not set"
  fi
done
```

### Security Check

```bash
# Verify no secrets in .env (compose level)
grep -E "(PASSWORD|SECRET|TOKEN|API_KEY)" .env && echo "WARNING: Secrets in .env"

# Verify no VITE_ secrets
grep -E "VITE_.*(SECRET|PASSWORD|TOKEN|KEY)" frontend/.env* && echo "ERROR: Secrets in frontend!"
```

---

## Migration Notes

### From Current to Target Structure

1. Move secrets from `/.env` to `/env/backend.env`
2. Update `docker-compose.yml` to use `env_file: ./env/backend.env`
3. Keep non-secrets in `/.env` for compose interpolation
4. Add `/env/` to `.gitignore`

### Backward Compatibility

During migration, both methods work:
- Direct environment variables in compose
- env_file directive

After migration, remove inline secrets from compose.

---

## Changelog

### Version 2.1 - 2025-12-24

**Updated:** Bot migrated to API-only architecture

**Major Changes:**
1. **Bot Runtime Secrets (Critical):**
   - Bot no longer requires `DB_*` variables (DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD)
   - Bot communicates ONLY via Django API (`BackendAPIClient`)
   - Added `X-Bot-Secret` header authentication between Bot and Backend
   - Updated docker-compose.yml to remove db dependency from bot service

2. **Removed from Bot:**
   - SQLAlchemy/Alembic (models, migrations, database services)
   - Direct PostgreSQL access
   - `django_integration.py` legacy service

3. **Security:**
   - `TELEGRAM_BOT_API_SECRET` is now required for Bot → Backend communication
   - Backend validates `X-Bot-Secret` header on all `/telegram/*` endpoints

---

### Version 2.0 - 2025-12-22

**Updated:** ENV documentation alignment with Docker build-args frontend architecture

**Major Changes:**
1. **Frontend Section (Critical):**
   - Removed all references to `.env.production` file
   - Added explicit warning that `.env.production` MUST NOT exist
   - Documented build-args flow: `docker-compose.yml` → Dockerfile ARG/ENV
   - Added security invariant: NO .env files in Docker images

2. **Bot Runtime Secrets:**
   - Added new dedicated section for bot configuration
   - Documented current state (docker-compose environment mapping)
   - Added recommended migration path to `env/bot.env`
   - Applied least-privilege principle

3. **Admin IDs Consolidation:**
   - Declared `TELEGRAM_ADMINS` as single source of truth
   - Marked `BOT_ADMIN_ID` and `ADMIN_IDS` as legacy
   - Added migration plan to remove duplicates

4. **Security Invariants (New Section):**
   - Added non-negotiable security rules
   - Production environment rules (DEBUG=False enforcement)
   - Secrets rules (no default values, strong generation)
   - CORS rules (no wildcard)
   - Admin lists rules (no auto-expansion)
   - Frontend security rules (no .env.production)
   - CI/CD and startup validation examples

5. **Rules Updates:**
   - Updated Rule A: Added explicit ban on `.env.production`
   - Updated Rule D: Changed frontend source from `.env.production` to `build.args`
   - Added enforcement requirements

**Reason:** Alignment with production security fixes from ENV_SECURITY_FIX_2025-12-21.md and actual Docker build architecture.

**Breaking Changes:**
- `.env.production` file is now explicitly forbidden
- Derived variables forbidden for security-critical values

**Migration Required:**
- Remove any existing `frontend/.env.production` files
- Ensure VITE variables defined in `docker-compose.yml` build.args
- Use only `TELEGRAM_ADMINS` for admin configuration
