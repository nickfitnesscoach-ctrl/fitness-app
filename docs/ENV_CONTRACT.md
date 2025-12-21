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
| `BOT_ADMIN_ID` | int | Yes | - | Primary admin Telegram ID |
| `ADMIN_IDS` | csv | No | - | Additional admin IDs |
| `TELEGRAM_ADMINS` | csv | Yes | - | Backend admin IDs |
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

**Location:** `/frontend/.env.production` (NOT in git, copied during build)
**Purpose:** Build-time variables embedded in JS bundle

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `VITE_API_URL` | path | No | /api/v1 | API base path |
| `VITE_TELEGRAM_BOT_NAME` | string | No | EatFit24_bot | Bot username |
| `VITE_TRAINER_INVITE_LINK` | url | No | https://t.me/EatFit24_bot | Trainer invite |

**Development only (never in production):**

| Variable | Type | Description |
|----------|------|-------------|
| `VITE_MOCK_TELEGRAM` | 0/1 | Mock Telegram WebApp |
| `VITE_SKIP_TG_AUTH` | bool | Skip auth check |

---

### 5. Bot Runtime Variables

**Location:** Inherits from compose + internal mapping
**Purpose:** Telegram bot configuration

Bot uses pydantic Settings with these mappings from compose:

| Bot Variable | Compose Variable | Notes |
|--------------|------------------|-------|
| `TELEGRAM_BOT_TOKEN` | `TELEGRAM_BOT_TOKEN` | Direct |
| `DB_HOST` | `POSTGRES_HOST` via mapping | Explicit in compose |
| `DB_PORT` | `POSTGRES_PORT` via mapping | Explicit in compose |
| `DB_NAME` | `POSTGRES_DB` via mapping | Explicit in compose |
| `DB_USER` | `POSTGRES_USER` via mapping | Explicit in compose |
| `DB_PASSWORD` | `POSTGRES_PASSWORD` via mapping | Explicit in compose |
| `OPENROUTER_API_KEY` | `OPENROUTER_API_KEY` | Direct |
| `WEB_APP_URL` | `WEB_APP_URL` | Direct |
| `TRAINER_PANEL_BASE_URL` | `TRAINER_PANEL_BASE_URL` | Direct |
| `DJANGO_API_URL` | `DJANGO_API_URL` | Direct |
| `ENVIRONMENT` | hardcoded | "production" in compose |

---

## Rules

### Rule A: Frontend Security

- All `VITE_*` variables are **PUBLIC** (embedded in JS bundle)
- **NEVER** put secrets in frontend env files
- **NEVER** use `VITE_` prefix for: API keys, tokens, passwords, secrets

### Rule B: Backend/Worker Secrets

- Secrets must be in `env/backend.env` or Docker secrets
- **NEVER** commit secrets to git
- **NEVER** use default/placeholder values in production
- Generate secrets with: `openssl rand -hex 32`

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
| `/frontend/.env.production` | Frontend build vars |
| `docker-compose.yml` | Hardcoded infra (redis URLs, ports) |

**Derived variables** (calculated from others) should have a comment explaining the source.

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
