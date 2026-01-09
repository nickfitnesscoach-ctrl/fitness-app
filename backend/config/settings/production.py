"""
config/settings/production.py — настройки PROD.

Правила:
- fail-fast на критические переменные
- APP_ENV обязан быть 'prod'
- запрещаем dev/test значения
- debug bypass выключен железно
"""

from __future__ import annotations

import os

from . import base

APP_ENV = os.environ.get("APP_ENV", "").strip().lower()
if APP_ENV != "prod":
    raise RuntimeError(f"[SAFETY] APP_ENV must be 'prod' in production, got: {APP_ENV!r}")

# SECRET_KEY обязателен
if not base.SECRET_KEY:
    raise RuntimeError("[SAFETY] SECRET_KEY must be set in production.")
SECRET_KEY = base.SECRET_KEY  # Export for Django to find

DEBUG = os.environ.get("DEBUG", "False").lower() == "true"
if DEBUG:
    raise RuntimeError("[SAFETY] DEBUG=True is forbidden in production.")

# Домены обязательны
_allowed_hosts_env = os.environ.get("ALLOWED_HOSTS", "").strip()
ALLOWED_HOSTS = [h.strip() for h in _allowed_hosts_env.split(",") if h.strip()]
if not ALLOWED_HOSTS:
    raise RuntimeError("[SAFETY] ALLOWED_HOSTS must be set in production.")

# -----------------------------------------------------------------------------
# Database (PROD only)
# -----------------------------------------------------------------------------

db_name = os.environ.get("POSTGRES_DB", "").strip()
db_user = os.environ.get("POSTGRES_USER", "").strip()
db_pass = os.environ.get("POSTGRES_PASSWORD", "").strip()

if not db_name or not db_user or not db_pass:
    raise RuntimeError("[SAFETY] POSTGRES_DB/USER/PASSWORD must be set in production.")

# Запрещаем dev/test имена
bad_markers = ("_dev", "test", "local")
if any(m in db_name for m in bad_markers):
    raise RuntimeError(f"[SAFETY] Forbidden DB name in production: {db_name!r}")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": db_name,
        "USER": db_user,
        "PASSWORD": db_pass,
        "HOST": os.environ.get("POSTGRES_HOST", "db"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 600,
    }
}

# -----------------------------------------------------------------------------
# Cache (Redis)
# -----------------------------------------------------------------------------

REDIS_URL = os.environ.get("REDIS_URL", "").strip()
if not REDIS_URL:
    raise RuntimeError("[SAFETY] REDIS_URL must be set in production (include password if used).")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        "KEY_PREFIX": "eatfit24",
        "TIMEOUT": 300,
    }
}

# -----------------------------------------------------------------------------
# Security hardening
# -----------------------------------------------------------------------------

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "True").lower() == "true"
CSRF_COOKIE_SECURE = os.environ.get("CSRF_COOKIE_SECURE", "True").lower() == "true"

SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "True").lower() == "true"

# CSRF trusted origins
_csrf_origins_env = os.environ.get("CSRF_TRUSTED_ORIGINS", "").strip()
if _csrf_origins_env:
    CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_origins_env.split(",") if o.strip()]
else:
    CSRF_TRUSTED_ORIGINS = [
        f"https://{host}" for host in ALLOWED_HOSTS if host not in ("localhost", "127.0.0.1")
    ]

# CORS origins
raw_origins = os.environ.get("CORS_ALLOWED_ORIGINS", "")
CORS_ALLOWED_ORIGINS = [o.strip() for o in raw_origins.split(",") if o.strip()]

# -----------------------------------------------------------------------------
# Telegram (PROD)
# -----------------------------------------------------------------------------

TELEGRAM_BOT_TOKEN = base.TELEGRAM_BOT_TOKEN
TELEGRAM_ADMINS = base.TELEGRAM_ADMINS

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("[SAFETY] TELEGRAM_BOT_TOKEN must be set in production.")

# ЖЕЛЕЗНО запрещаем debug bypass в production
WEBAPP_DEBUG_MODE_ENABLED = False

# -----------------------------------------------------------------------------
# Billing (YooKassa)
# -----------------------------------------------------------------------------

YOOKASSA_SHOP_ID = base.YOOKASSA_SHOP_ID
YOOKASSA_SECRET_KEY = base.YOOKASSA_SECRET_KEY

YOOKASSA_MODE = os.environ.get("YOOKASSA_MODE", "prod").strip().lower()
if YOOKASSA_MODE != "prod":
    raise RuntimeError("[SAFETY] YOOKASSA_MODE must be 'prod' in production.")

if not YOOKASSA_SHOP_ID or not YOOKASSA_SECRET_KEY:
    raise RuntimeError("[SAFETY] YooKassa credentials missing in production.")

if YOOKASSA_SECRET_KEY.startswith("test_"):
    raise RuntimeError("[SAFETY] Test YooKassa key detected in production.")

YOOKASSA_RETURN_URL = base.YOOKASSA_RETURN_URL
YOOKASSA_WEBHOOK_URL = base.YOOKASSA_WEBHOOK_URL
YOOKASSA_WEBHOOK_VERIFY_SIGNATURE = base.YOOKASSA_WEBHOOK_VERIFY_SIGNATURE

BILLING_RECURRING_ENABLED = os.environ.get("BILLING_RECURRING_ENABLED", "false").lower() == "true"

# -----------------------------------------------------------------------------
# Trusted proxies for audit logs
# -----------------------------------------------------------------------------

TRUSTED_PROXIES_ENABLED = base.TRUSTED_PROXIES_ENABLED
TRUSTED_PROXIES = base.TRUSTED_PROXIES

# -----------------------------------------------------------------------------
# Static
# -----------------------------------------------------------------------------

STATIC_URL = base.STATIC_URL
STATIC_ROOT = base.STATIC_ROOT
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = base.MEDIA_URL
MEDIA_ROOT = base.MEDIA_ROOT

# -----------------------------------------------------------------------------
# Rest of settings from base
# -----------------------------------------------------------------------------

INSTALLED_APPS = base.INSTALLED_APPS
MIDDLEWARE = base.MIDDLEWARE
ROOT_URLCONF = base.ROOT_URLCONF
WSGI_APPLICATION = base.WSGI_APPLICATION
TEMPLATES = base.TEMPLATES

LANGUAGE_CODE = base.LANGUAGE_CODE
TIME_ZONE = base.TIME_ZONE
USE_I18N = base.USE_I18N
USE_TZ = base.USE_TZ

DEFAULT_AUTO_FIELD = base.DEFAULT_AUTO_FIELD
SPECTACULAR_SETTINGS = base.SPECTACULAR_SETTINGS

REST_FRAMEWORK = base.REST_FRAMEWORK
SIMPLE_JWT = base.SIMPLE_JWT

AI_PROXY_URL = base.AI_PROXY_URL
AI_PROXY_SECRET = base.AI_PROXY_SECRET
AI_ASYNC_ENABLED = base.AI_ASYNC_ENABLED

CELERY_BROKER_URL = base.CELERY_BROKER_URL
CELERY_RESULT_BACKEND = base.CELERY_RESULT_BACKEND
CELERY_ACCEPT_CONTENT = base.CELERY_ACCEPT_CONTENT
CELERY_TASK_SERIALIZER = base.CELERY_TASK_SERIALIZER
CELERY_RESULT_SERIALIZER = base.CELERY_RESULT_SERIALIZER
CELERY_TIMEZONE = base.CELERY_TIMEZONE
CELERY_TASK_TRACK_STARTED = base.CELERY_TASK_TRACK_STARTED
CELERY_TASK_TIME_LIMIT = base.CELERY_TASK_TIME_LIMIT
CELERY_TASK_ROUTES = base.CELERY_TASK_ROUTES

# Логи в stdout
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "apps.telegram": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "apps.common.audit": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
