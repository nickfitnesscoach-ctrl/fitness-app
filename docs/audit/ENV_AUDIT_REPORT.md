# ENV Audit Report - EatFit24

**Date:** 2025-12-21
**Status:** CRITICAL ISSUES FOUND
**Auditor:** Claude Code

---

## Executive Summary

| Category | Status |
|----------|--------|
| Security | :red_circle: CRITICAL |
| Dev/Prod Parity | :warning: WARNING |
| Structure | :warning: WARNING |
| Documentation | :white_check_mark: OK |

### Top-7 Risks

1. **:red_circle: P0** - `DEBUG=True` hardcoded in docker-compose.yml for production backend
2. **:red_circle: P0** - `DEBUG_MODE_ENABLED=True` in production container (allows unauthorized access)
3. **:red_circle: P0** - `AI_PROXY_SECRET=changeme_long_random_string` - default secret in production
4. **:red_circle: P0** - Wildcard CORS (`Access-Control-Allow-Origin *`) in nginx.conf
5. **:warning: P1** - Duplicate `DJANGO_API_URL` definition in .env (lines 44 and 81)
6. **:warning: P1** - `ALLOWED_HOSTS` has duplicate at end of .env (line 87 overwrites line 17)
7. **:warning: P2** - Bot uses different DB variable naming (`DB_*` vs `POSTGRES_*`)

---

## Inventory

### ENV Files Map

| File | Location | Used By | In Git | Purpose |
|------|----------|---------|--------|---------|
| `.env` | root | docker-compose.yml | No (.gitignore) | Compose-level + secrets |
| `.env.example` | root | - | Yes | Template |
| `.env.production` | frontend/ | Dockerfile COPY | No (.gitignore) | Frontend build vars |
| `.env.development` | frontend/ | Vite dev server | No (.gitignore) | Frontend dev vars |
| `.env.example` | frontend/ | - | Yes | Frontend template |
| `.env.example` | bot/ | - | Yes | Bot template |

### Variables Inventory

#### Compose-Level (docker-compose.yml)

| Variable | Scope | Sensitive | Status | Notes |
|----------|-------|-----------|--------|-------|
| `POSTGRES_DB` | db, backend, worker, bot | No | OK | |
| `POSTGRES_USER` | db, backend, worker, bot | No | OK | |
| `POSTGRES_PASSWORD` | db, backend, worker, bot | **YES** | OK | Should be in secrets |
| `SECRET_KEY` | backend, worker, beat | **YES** | OK | Should be in secrets |
| `DEBUG` | backend | No | **WRONG** | Hardcoded `True` in compose |
| `DEBUG_MODE_ENABLED` | backend, worker | No | **WRONG** | Hardcoded `True` in compose |
| `ALLOWED_HOSTS` | backend, worker, beat | No | **DUPLICATE** | Also in .env line 87 |
| `CORS_ALLOWED_ORIGINS` | backend | No | OK | |
| `TELEGRAM_BOT_TOKEN` | backend, worker, beat, bot | **YES** | OK | |
| `TELEGRAM_BOT_API_SECRET` | backend, bot | **YES** | OK | |
| `BOT_ADMIN_ID` | backend, bot | No | OK | |
| `ADMIN_IDS` | bot | No | OK | |
| `TELEGRAM_ADMINS` | backend, worker, beat, bot | No | OK | Appended with `,999999999` |
| `OPENROUTER_API_KEY` | backend, worker, bot | **YES** | OK | |
| `SWAGGER_AUTH_USERNAME` | backend | No | OK | |
| `SWAGGER_AUTH_PASSWORD` | backend | **YES** | OK | |
| `YOOKASSA_MODE` | backend | No | OK | |
| `YOOKASSA_SHOP_ID_TEST` | backend | No | OK | |
| `YOOKASSA_API_KEY_TEST` | backend | **YES** | OK | |
| `YOOKASSA_SHOP_ID_PROD` | backend | No | OK | |
| `YOOKASSA_API_KEY_PROD` | backend | **YES** | OK | |
| `YOOKASSA_RETURN_URL` | backend | No | OK | |
| `WEBHOOK_TRUST_XFF` | backend | No | OK | |
| `WEBHOOK_TRUSTED_PROXIES` | backend | No | OK | |
| `BILLING_RECURRING_ENABLED` | backend | No | OK | |
| `AI_PROXY_URL` | backend, worker | No | OK | |
| `AI_PROXY_SECRET` | backend, worker | **YES** | **WRONG** | Default value in prod |
| `AI_ASYNC_ENABLED` | backend, worker | No | OK | |
| `WEB_APP_URL` | bot | No | OK | |
| `TRAINER_PANEL_BASE_URL` | bot | No | OK | |
| `DJANGO_API_URL` | bot | No | **DUPLICATE** | Defined twice in .env |

#### Frontend (VITE_*)

| Variable | Sensitive | Status | Notes |
|----------|-----------|--------|-------|
| `VITE_API_URL` | No | OK | Relative path `/api/v1` |
| `VITE_TELEGRAM_BOT_NAME` | No | OK | |
| `VITE_TRAINER_INVITE_LINK` | No | OK | |
| `VITE_MOCK_TELEGRAM` | No | OK | Dev only |
| `VITE_SKIP_TG_AUTH` | No | OK | Dev only |
| `VITE_WEBAPP_URL` | No | OK | Server only |
| `VITE_ENV` | No | OK | Server only |

#### Bot-Specific (pydantic Settings)

| Variable | Maps From | Status | Notes |
|----------|-----------|--------|-------|
| `DB_HOST` | - | OK | Different naming than POSTGRES_* |
| `DB_PORT` | - | OK | |
| `DB_NAME` | - | OK | |
| `DB_USER` | - | OK | |
| `DB_PASSWORD` | - | OK | |
| `ENVIRONMENT` | - | OK | |
| `OPENROUTER_MODEL` | - | OK | |
| `OPENROUTER_TIMEOUT` | - | OK | |

---

## Findings

### P0 - Critical (Immediate Fix Required)

#### P0-001: DEBUG=True in Production

**Fact:** `docker-compose.yml:67` hardcodes `DEBUG=True` for backend container.

**Risk:**
- Exposes detailed error tracebacks to users
- Enables Django Debug Toolbar if installed
- Leaks internal paths and settings

**Fix:**
```yaml
# docker-compose.yml line 67
- DEBUG=True
+ DEBUG=${DEBUG:-False}
```

---

#### P0-002: DEBUG_MODE_ENABLED=True in Production

**Fact:** `docker-compose.yml:92` and `:135` hardcode `DEBUG_MODE_ENABLED=True`.

**Risk:**
- Allows `X-Debug-Mode: true` header to bypass Telegram authentication
- Anyone can impersonate debug user (ID 999999999)
- Full access to trainer panel without auth

**Current server state:**
```
DEBUG_MODE_ENABLED=True (in container env)
```

**Fix:**
```yaml
# docker-compose.yml lines 92, 135
- DEBUG_MODE_ENABLED=True
+ DEBUG_MODE_ENABLED=${DEBUG_MODE_ENABLED:-False}
```

---

#### P0-003: Default AI_PROXY_SECRET in Production

**Fact:** `.env` contains `AI_PROXY_SECRET=changeme_long_random_string`

**Risk:**
- AI Proxy authentication is effectively disabled
- Anyone who discovers the endpoint can use it

**Fix:**
1. Generate secure secret: `openssl rand -hex 32`
2. Update `.env` on server
3. Update AI Proxy service with same secret

---

#### P0-004: Wildcard CORS in nginx.conf

**Fact:** `frontend/nginx.conf:40` has `add_header Access-Control-Allow-Origin * always;`

**Risk:**
- Any website can make authenticated API requests
- Combined with P0-002, creates full auth bypass

**Fix:**
```nginx
# Remove or comment out:
# add_header Access-Control-Allow-Origin * always;
# Django CORS middleware handles this properly
```

---

### P1 - High Priority

#### P1-001: Duplicate DJANGO_API_URL

**Fact:** `.env` defines `DJANGO_API_URL` twice (lines 44 and 81).

**Risk:** Confusion, potential misconfiguration.

**Fix:** Remove duplicate on line 44.

---

#### P1-002: Duplicate/Conflicting ALLOWED_HOSTS

**Fact:**
- Line 17: `ALLOWED_HOSTS=localhost,backend,eatfit24.ru,www.eatfit24.ru`
- Line 87: `ALLOWED_HOSTS=localhost,127.0.0.1`

**Risk:** Line 87 overwrites line 17, may break production.

**Fix:** Remove line 87 or merge values.

---

#### P1-003: TELEGRAM_ADMINS Appended with 999999999

**Fact:** `docker-compose.yml` appends `,999999999` to TELEGRAM_ADMINS for backend, worker, bot.

**Risk:** Debug user ID has admin privileges even in production.

**Fix:**
```yaml
# Remove ,999999999 suffix
- TELEGRAM_ADMINS=${TELEGRAM_ADMINS},999999999
+ TELEGRAM_ADMINS=${TELEGRAM_ADMINS}
```

---

#### P1-004: Bot Uses Different DB Variable Names

**Fact:** Bot expects `DB_*` but compose passes `POSTGRES_*` via mapping.

**Risk:** Confusion in configuration, potential mismatch.

**Current mapping (correct but implicit):**
```yaml
- DB_NAME=${POSTGRES_DB:-eatfit24}
- DB_USER=${POSTGRES_USER:-eatfit24}
- DB_PASSWORD=${POSTGRES_PASSWORD}
```

**Recommendation:** Document this mapping in ENV_CONTRACT.md.

---

### P2 - Medium Priority

#### P2-001: No Separate env Files for Runtime Secrets

**Fact:** All secrets in single root `.env` file.

**Risk:**
- Larger blast radius if file exposed
- No separation of concerns

**Fix:** Implement target design with `env/` directory.

---

#### P2-002: frontend/.env.production Not in .gitignore Root

**Fact:** Root `.gitignore` has `frontend/.env` but frontend has its own `.gitignore` with `.env.*`.

**Risk:** Confusion about what's tracked.

**Status:** OK - both gitignores exclude correctly.

---

### P3 - Low Priority

#### P3-001: Inconsistent Naming (YOOKASSA_SECRET_KEY vs YOOKASSA_API_KEY_*)

**Fact:** `.env` has both `YOOKASSA_SECRET_KEY` and `YOOKASSA_API_KEY_TEST/PROD`.

**Risk:** Confusion about which to use.

**Note:** Code uses `YOOKASSA_API_KEY_*` based on mode, `YOOKASSA_SECRET_KEY` is legacy.

---

#### P3-002: Old Backup .env Files on Server

**Fact:** Server has `.env.backup_*` files from Nov 2025.

**Risk:** Potential secret exposure if readable.

**Fix:** Remove or secure old backups.

---

## Server State vs Target

| Aspect | Current State | Target State | Gap |
|--------|--------------|--------------|-----|
| `.env` location | `/opt/EatFit24/.env` | Same | OK |
| `env/` directory | Not exists | Create for secrets | TODO |
| DEBUG | True in container | False | **CRITICAL** |
| DEBUG_MODE_ENABLED | True in container | False | **CRITICAL** |
| Secrets separation | All in .env | Separate files | TODO |
| frontend/.env.production | Has extra vars | Minimal VITE_* | Review |

---

## Target Design

### File Structure

```
/opt/EatFit24/
├── .env                    # Compose-level (non-secrets)
├── .env.example            # Template (in git)
├── env/                    # Runtime secrets (NOT in git)
│   ├── backend.env         # Backend + worker secrets
│   └── bot.env             # Bot-specific if needed
├── docker-compose.yml
└── ...
```

### .env (Compose-Level, No Secrets)

```bash
# Environment
COMPOSE_PROJECT_NAME=eatfit24
ENVIRONMENT=production

# Database (non-secret)
POSTGRES_DB=foodmind
POSTGRES_HOST=db
POSTGRES_PORT=5432

# URLs (public)
ALLOWED_HOSTS=localhost,backend,eatfit24.ru,www.eatfit24.ru
CORS_ALLOWED_ORIGINS=https://eatfit24.ru,https://www.eatfit24.ru
WEB_APP_URL=https://eatfit24.ru
TRAINER_PANEL_BASE_URL=https://eatfit24.ru/app
DJANGO_API_URL=http://backend:8000/api/v1
YOOKASSA_RETURN_URL=https://t.me/EatFit24_bot

# Feature flags
DEBUG=False
DEBUG_MODE_ENABLED=False
AI_ASYNC_ENABLED=True
BILLING_RECURRING_ENABLED=false
YOOKASSA_MODE=prod

# Admin IDs (not secret, just config)
BOT_ADMIN_ID=310151740
ADMIN_IDS=310151740
TELEGRAM_ADMINS=310151740

# Webhook config
WEBHOOK_TRUST_XFF=true
WEBHOOK_TRUSTED_PROXIES=127.0.0.1,172.23.0.0/16
```

### env/backend.env (Secrets)

```bash
# Database
POSTGRES_USER=foodmind
POSTGRES_PASSWORD=<GENERATE_NEW>

# Django
SECRET_KEY=<GENERATE_NEW>

# Telegram
TELEGRAM_BOT_TOKEN=<KEEP_CURRENT>
TELEGRAM_BOT_API_SECRET=<KEEP_CURRENT>

# API Keys
OPENROUTER_API_KEY=<KEEP_CURRENT>

# Swagger
SWAGGER_AUTH_USERNAME=admin
SWAGGER_AUTH_PASSWORD=<GENERATE_NEW>

# YooKassa
YOOKASSA_SHOP_ID_TEST=1201077
YOOKASSA_API_KEY_TEST=<KEEP_CURRENT>
YOOKASSA_SHOP_ID_PROD=1195531
YOOKASSA_API_KEY_PROD=<KEEP_CURRENT>

# AI Proxy
AI_PROXY_URL=http://185.171.80.128:8001
AI_PROXY_SECRET=<GENERATE_NEW>
```

---

## Migration Plan

### Phase 1: Fix Critical Issues (No Downtime)

1. **Fix docker-compose.yml** - Remove hardcoded DEBUG values
2. **Update .env on server** - Set `DEBUG=False`, `DEBUG_MODE_ENABLED=False`
3. **Generate new AI_PROXY_SECRET** - Update both backend and AI Proxy
4. **Fix nginx.conf** - Remove wildcard CORS
5. **Redeploy all services**

### Phase 2: Restructure (Planned Maintenance)

1. Create `env/` directory on server
2. Move secrets to `env/backend.env`
3. Update docker-compose.yml to use `env_file`
4. Test locally with new structure
5. Deploy to server

### Phase 3: Cleanup

1. Remove duplicate variables from .env
2. Clean up old backup files on server
3. Update .env.example templates
4. Document in ENV_CONTRACT.md

---

## Verification Checklist

After applying fixes:

```bash
# 1. Check DEBUG is False
ssh root@eatfit24.ru "docker exec eatfit24-backend-1 printenv DEBUG"
# Expected: False (or empty)

# 2. Check DEBUG_MODE_ENABLED is False
ssh root@eatfit24.ru "docker exec eatfit24-backend-1 printenv DEBUG_MODE_ENABLED"
# Expected: False (or empty)

# 3. Verify debug mode is rejected
curl -H "X-Debug-Mode: true" https://eatfit24.ru/api/v1/nutrition/diary/
# Expected: 401 Unauthorized

# 4. Check CORS header not wildcard
curl -I -X OPTIONS https://eatfit24.ru/api/v1/ -H "Origin: https://evil.com"
# Expected: No Access-Control-Allow-Origin or specific domain only

# 5. Health check
curl https://eatfit24.ru/api/v1/health/
# Expected: {"status":"ok"}

# 6. Frontend loads
curl -I https://eatfit24.ru/app/
# Expected: 200 OK
```

---

## Appendix: Files Changed

| File | Changes Needed |
|------|----------------|
| `docker-compose.yml` | Remove hardcoded DEBUG, DEBUG_MODE_ENABLED, TELEGRAM_ADMINS suffix |
| `.env` (server) | Remove duplicates, set DEBUG=False |
| `frontend/nginx.conf` | Remove wildcard CORS |
| `.gitignore` | Add `env/` exclusion |
| `env/backend.env` | Create (not in git) |
