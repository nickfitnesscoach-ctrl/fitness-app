# Security Fix Report - 2025-12-21

## Critical Auth Bypass Vulnerability - FIXED

### Executive Summary

**Severity:** CRITICAL
**Status:** FIXED
**Date:** 2025-12-21
**Affected Systems:** Production (eatfit24.ru)

A combination of misconfigurations created a **full authentication bypass** allowing any attacker to gain admin access to the system.

---

## Vulnerability Chain

```
Wildcard CORS (nginx)
    + DEBUG_MODE_ENABLED=True (hardcoded)
    + TELEGRAM_ADMINS+=999999999 (debug user as admin)
    = Full Auth Bypass
```

### Proof of Concept (Before Fix)

```bash
# Anyone could execute this and get full admin access:
curl -H "X-Debug-Mode: true" \
     -H "X-Debug-User-Id: 999999999" \
     https://eatfit24.ru/api/v1/trainer-panel/clients/
# Result: Full access to all client data
```

---

## Issues Found

### P0-001: DEBUG=True in Production

**Location:** `docker-compose.yml:67`

**Before:**
```yaml
- DEBUG=True
```

**After:**
```yaml
- DEBUG=${DEBUG:-False}
```

**Risk:** Exposed detailed error tracebacks, internal paths, settings.

---

### P0-002: DEBUG_MODE_ENABLED=True in Production

**Location:** `docker-compose.yml:92, 135`

**Before:**
```yaml
- DEBUG_MODE_ENABLED=True
```

**After:**
```yaml
- DEBUG_MODE_ENABLED=${DEBUG_MODE_ENABLED:-False}
```

**Risk:** Allowed `X-Debug-Mode: true` header to bypass Telegram authentication completely. Anyone could impersonate any user.

---

### P0-003: Admin Backdoor (999999999)

**Location:** `docker-compose.yml:74, 137, 200`

**Before:**
```yaml
- TELEGRAM_ADMINS=${TELEGRAM_ADMINS},999999999
```

**After:**
```yaml
- TELEGRAM_ADMINS=${TELEGRAM_ADMINS}
```

**Risk:** Debug user ID had full admin privileges in production.

---

### P0-004: Wildcard CORS

**Location:** `frontend/nginx.conf:40-46`

**Before:**
```nginx
add_header Access-Control-Allow-Origin * always;
add_header Access-Control-Allow-Methods "GET, POST, PUT, PATCH, DELETE, OPTIONS" always;
add_header Access-Control-Allow-Headers "..." always;

if ($request_method = OPTIONS) {
    return 204;
}
```

**After:**
```nginx
# CORS handled by Django middleware (corsheaders)
# DO NOT add wildcard CORS here - security risk!
# Django CORS_ALLOWED_ORIGINS controls which origins are allowed
```

**Risk:** Any malicious website could make authenticated requests to the API on behalf of users.

---

### P0-005: Default AI_PROXY_SECRET

**Location:** `.env` on both servers

**Before:**
```
AI_PROXY_SECRET=changeme_long_random_string
```

**After:**
```
AI_PROXY_SECRET=c6b837b17429b1e7b488cc6333759dce6a326b9f6cee73a1c228670867a44a5c
```

**Risk:** AI Proxy authentication was effectively disabled.

---

## Additional Fixes

### Server .env Cleanup

- Removed duplicate `DJANGO_API_URL` (was defined twice)
- Removed conflicting `ALLOWED_HOSTS` at end of file
- Set `DEBUG=False` and `DEBUG_MODE_ENABLED=False`
- Removed old `.env.backup_*` files (potential secret exposure)

### AI Proxy Network Fix

**Location:** AI Proxy server `/opt/eatfit24-ai-proxy/docker-compose.yml`

**Before:**
```yaml
ports:
  - "127.0.0.1:8001:8001"
```

**After:**
```yaml
ports:
  - "0.0.0.0:8001:8001"
```

Backend couldn't reach AI Proxy because it was bound to localhost only.

---

## Verification

### After Fix - All Tests Pass

```bash
# 1. Debug mode blocked
curl -H "X-Debug-Mode: true" https://eatfit24.ru/api/v1/billing/subscription/
# {"error":{"code":"UNAUTHORIZED","message":"Debug mode is disabled"}}

# 2. CORS blocks malicious origins
curl -I -X OPTIONS https://eatfit24.ru/api/v1/health/ -H "Origin: https://evil.com"
# No Access-Control-Allow-Origin header

# 3. CORS allows legitimate origin
curl -I -X OPTIONS https://eatfit24.ru/api/v1/health/ -H "Origin: https://eatfit24.ru"
# access-control-allow-origin: https://eatfit24.ru

# 4. AI Proxy rejects wrong key
curl -X POST http://185.171.80.128:8001/api/v1/ai/recognize-food \
     -H "X-API-Key: wrong" -d '{}'
# {"detail":"Invalid or missing API key"}

# 5. Container env vars correct
docker exec eatfit24-backend-1 printenv | grep DEBUG
# DEBUG=False
# DEBUG_MODE_ENABLED=False
```

---

## Files Changed

| File | Changes |
|------|---------|
| `docker-compose.yml` | Removed hardcoded DEBUG, DEBUG_MODE_ENABLED, admin backdoor |
| `frontend/nginx.conf` | Removed wildcard CORS |
| `.env` (server) | Fixed DEBUG values, removed duplicates |
| AI Proxy `.env` | New secret |
| AI Proxy `docker-compose.yml` | Fixed port binding |

---

## Commits

1. `14f2544` - fix(security): CRITICAL - close auth bypass vulnerabilities

---

## Recommendations

### Immediate (Done)

- [x] Fix DEBUG flags
- [x] Remove admin backdoor
- [x] Remove wildcard CORS
- [x] Generate new AI_PROXY_SECRET
- [x] Clean up .env duplicates and backups

### Short-term

- [ ] Add CI check: fail build if `DEBUG=True` or `changeme` in env
- [ ] Implement `env/` directory structure for secrets separation
- [ ] Add startup log that prints ENVIRONMENT and DEBUG status

### Long-term

- [ ] Rotate all secrets (POSTGRES_PASSWORD, SECRET_KEY, etc.)
- [ ] Set up secrets management (Vault, AWS Secrets Manager)
- [ ] Add security scanning to CI/CD pipeline

---

## Timeline

| Time | Action |
|------|--------|
| 13:45 | Audit started |
| 14:10 | Critical issues identified |
| 14:25 | Fixes applied to code |
| 14:30 | Deployed to production |
| 14:35 | Verification complete |
| 14:45 | AI_PROXY_SECRET rotated |
| 14:50 | All services verified working |

---

## Contact

If you discover any security issues, contact the development team immediately.
