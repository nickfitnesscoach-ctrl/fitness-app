# Environment Variables Audit — Production vs Contract

**Server:** 85.198.81.133 (eatfit24.ru)
**Date:** 2025-12-26
**Container:** eatfit24-backend

---

## 📋 Summary

**Total ENV variables:** 47
**Critical missing (pre-fix):** 2
**Status after fix:** ✅ ALL REQUIRED VARIABLES PRESENT

---

## 🔴 Critical Missing Variables (BEFORE FIX)

| Variable | Required | Status | Impact |
|----------|----------|--------|--------|
| `AI_PROXY_URL` | ✅ YES | ❌ MISSING | **CRITICAL:** AI recognition completely broken |
| `AI_PROXY_SECRET` | ✅ YES | ❌ MISSING | **CRITICAL:** Cannot authenticate to AI-proxy |

**Result:** AI recognition service was **completely non-functional**.

---

## ✅ Critical Variables (AFTER FIX)

| Variable | Value | Status | Source |
|----------|-------|--------|--------|
| `AI_PROXY_URL` | `http://185.171.80.128:8001` | ✅ SET | `.env` |
| `AI_PROXY_SECRET` | `c6b837b17...` (masked) | ✅ SET | `.env` |
| `OPENAI_API_KEY` | `sk-or-v1-...` (OpenRouter) | ✅ SET | `.env` |
| `AI_ASYNC_ENABLED` | `true` | ✅ SET | `.env` |
| `AI_RATE_LIMIT_PER_MINUTE` | `60` | ✅ SET | `.env` |

---

## 📊 Full Environment Review

### Django Core
| Variable | Value | Status |
|----------|-------|--------|
| `DJANGO_SETTINGS_MODULE` | `config.settings.production` | ✅ |
| `DJANGO_SECRET_KEY` | `fd4^&!4of...` | ✅ |
| `DEBUG` | `false` | ✅ |
| `ENV` | `production` | ✅ |
| `DOMAIN_NAME` | `eatfit24.ru` | ✅ |
| `ALLOWED_HOSTS` | `eatfit24.ru,www.eatfit24.ru,...` | ✅ |

### Database
| Variable | Value | Status |
|----------|-------|--------|
| `DATABASE_URL` | `postgres://eatfit24:***@db:5432/eatfit24` | ✅ |
| `POSTGRES_HOST` | `db` | ✅ |
| `POSTGRES_PORT` | `5432` | ✅ |
| `POSTGRES_DB` | `eatfit24` | ✅ |
| `POSTGRES_USER` | `eatfit24` | ✅ |
| `POSTGRES_PASSWORD` | `***` (masked) | ✅ |

### Cache & Celery
| Variable | Value | Status |
|----------|-------|--------|
| `REDIS_URL` | `redis://redis:6379/0` | ✅ |
| `CELERY_BROKER_URL` | `redis://redis:6379/0` | ✅ |
| `CELERY_RESULT_BACKEND` | `redis://redis:6379/0` | ✅ |
| `CELERY_TASK_ALWAYS_EAGER` | `false` | ✅ |
| `CELERY_TIMEZONE` | `UTC` | ✅ |
| `DJANGO_CACHE_BACKEND` | `redis` | ✅ |

### AI & Recognition
| Variable | Value | Status |
|----------|-------|--------|
| `AI_PROXY_URL` | `http://185.171.80.128:8001` | ✅ FIXED |
| `AI_PROXY_SECRET` | `c6b837b17...` | ✅ FIXED |
| `OPENAI_API_KEY` | `sk-or-v1-...` (OpenRouter) | ✅ |
| `AI_ASYNC_ENABLED` | `true` | ✅ |
| `AI_RATE_LIMIT_PER_MINUTE` | `60` | ✅ |

### Billing (YooKassa)
| Variable | Value | Status |
|----------|-------|--------|
| `YOOKASSA_SHOP_ID` | `1195531` | ✅ |
| `YOOKASSA_SECRET_KEY` | `live_YMbX...` | ✅ |
| `YOOKASSA_MODE` | `prod` | ✅ |
| `YOOKASSA_RETURN_URL` | `https://eatfit24.ru/payment-success` | ✅ |
| `YOOKASSA_WEBHOOK_URL` | `https://eatfit24.ru/api/billing/webhook/yookassa/` | ✅ |
| `YOOKASSA_WEBHOOK_VERIFY_SIGNATURE` | `true` | ✅ |
| `BILLING_RECURRING_ENABLED` | `false` | ⚠️ Disabled (known issue) |
| `BILLING_STRICT_MODE` | `true` | ✅ |
| `BILLING_LOG_EVENTS` | `true` | ✅ |

### Security
| Variable | Value | Status |
|----------|-------|--------|
| `CSRF_COOKIE_SECURE` | `true` | ✅ |
| `SESSION_COOKIE_SECURE` | `true` | ✅ |
| `SECURE_SSL_REDIRECT` | `true` | ✅ |
| `SECURE_HSTS_SECONDS` | `31536000` | ✅ |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | `true` | ✅ |
| `SECURE_HSTS_PRELOAD` | `true` | ✅ |
| `CSRF_TRUSTED_ORIGINS` | `https://eatfit24.ru,https://www.eatfit24.ru` | ✅ |
| `ALLOWED_RETURN_URL_DOMAINS` | `eatfit24.ru,localhost` | ✅ |

### Static Files
| Variable | Value | Status |
|----------|-------|--------|
| `STATIC_ROOT` | `/app/staticfiles` | ✅ |
| `STATIC_URL` | `/static/` | ✅ |
| `MEDIA_ROOT` | `/app/media` | ✅ |
| `MEDIA_URL` | `/media/` | ✅ |
| `STATICFILES_STORAGE` | `whitenoise.storage.CompressedManifestStaticFilesStorage` | ✅ |

### Telegram
| Variable | Value | Status |
|----------|-------|--------|
| `TELEGRAM_BOT_TOKEN` | `7611657073:AAG...` | ✅ |
| `TELEGRAM_ADMIN_ID` | `310151740` | ✅ |

### Swagger/API Docs
| Variable | Value | Status |
|----------|-------|--------|
| `SWAGGER_ENABLED` | `true` | ✅ |
| `SWAGGER_AUTH_USERNAME` | `admin` | ✅ |
| `SWAGGER_AUTH_PASSWORD` | `8fK9sLQx_2HkA7` | ✅ |

### Django Operational
| Variable | Value | Status |
|----------|-------|--------|
| `RUN_MIGRATIONS` | `true` | ✅ |
| `RUN_COLLECTSTATIC` | `true` | ✅ |
| `MIGRATIONS_STRICT` | `1` | ✅ |

---

## 🔍 Contract Validation

### Backend Settings Contract
**File:** `backend/config/settings/base.py`

**Required Variables (from code):**
```python
# Line 280-281
AI_PROXY_URL = os.environ.get("AI_PROXY_URL", "")      # ✅ NOW SET
AI_PROXY_SECRET = os.environ.get("AI_PROXY_SECRET", "")  # ✅ NOW SET
```

**Validation in code:**
```python
# apps/ai_proxy/client.py:62-65
if not url:
    raise AIProxyServerError("AI_PROXY_URL не задан в настройках Django")
if not secret:
    raise AIProxyAuthenticationError("AI_PROXY_SECRET не задан в настройках Django")
```

**Status:** ✅ PASS (after fix)

---

## ⚠️ Known Issues & Caveats

### 1. BILLING_RECURRING_ENABLED = false
**Reason:** YooKassa account doesn't have recurring payments feature enabled
**Impact:** Auto-renewal не работает (требуется связаться с YooKassa)
**Workaround:** Feature flag отключён до активации на стороне YooKassa

### 2. AI-proxy на отдельном сервере
**Current:** 185.171.80.128:8001
**Protocol:** HTTP (не HTTPS)
**Security:** Внутренняя сеть, но рекомендуется VPN или HTTPS в будущем

---

## 📝 Recommendations

### P0 (Critical)
1. ✅ **DONE:** Add `AI_PROXY_URL` and `AI_PROXY_SECRET` to `.env`
2. ⚠️ **TODO:** Create `.env.example` with all required variables
3. ⚠️ **TODO:** Add startup validation script to check critical ENV vars

### P1 (High)
1. Document minimum required ENV for production deployment
2. Add healthcheck that validates ENV before starting app
3. Consider centralizing ENV management (vault, secrets manager)

### P2 (Medium)
1. Implement ENV variable rotation policy for secrets
2. Audit and remove unused ENV variables
3. Standardize ENV variable naming convention

---

## ✅ Final Verdict

**Before Fix:** ❌ **CRITICAL FAILURE** - Missing AI_PROXY variables
**After Fix:** ✅ **PASS** - All required variables present and validated

**Production readiness:** ✅ **READY** (AI service operational)

---

**Audit Date:** 2025-12-26
**Next Review:** After deploying any new features requiring ENV changes
