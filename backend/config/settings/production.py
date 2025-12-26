"""
production.py — настройки для продакшена (сервер).

Простыми словами:
- DEBUG выключен
- ALLOWED_HOSTS обязателен (иначе Django блокирует запросы)
- cache = Redis
- включены базовые security-настройки (cookies, HSTS, и т.д.)
"""

from __future__ import annotations

import os

from .base import *  # noqa

# SECRET_KEY validation for production
if not SECRET_KEY:  # noqa: F405
    raise ValueError("SECRET_KEY must be set in production environment")

DEBUG = os.environ.get("DEBUG", "False").lower() == "true"

# В проде обязательно указывать домены
_allowed_hosts_env = os.environ.get("ALLOWED_HOSTS", "").strip()
ALLOWED_HOSTS = [h.strip() for h in _allowed_hosts_env.split(",") if h.strip()]
if not ALLOWED_HOSTS:
    raise ValueError("ALLOWED_HOSTS должен быть задан в продакшене")


# -----------------------------------------------------------------------------
# Database: прод = PostgreSQL (можно добавить pooling)
# -----------------------------------------------------------------------------
DATABASES["default"]["CONN_MAX_AGE"] = 600  # noqa: F405


# -----------------------------------------------------------------------------
# Cache: прод = Redis
# -----------------------------------------------------------------------------
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/1")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        "KEY_PREFIX": "eatfit24",
        "TIMEOUT": 300,
    }
}


# -----------------------------------------------------------------------------
# Security (минимальный hardening)
# -----------------------------------------------------------------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "True").lower() == "true"
CSRF_COOKIE_SECURE = os.environ.get("CSRF_COOKIE_SECURE", "True").lower() == "true"

SECURE_HSTS_SECONDS = 31536000  # 1 год
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Перенаправление на HTTPS
# Defense in depth: Django тоже делает редирект, даже если внешний Nginx уже настроен
# Помогает при обходе Nginx (внутренний доступ, неправильный vhost, будущие прокси-сценарии)
SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "True").lower() == "true"


# -----------------------------------------------------------------------------
# CSRF: trusted origins для Django 4.0+ (требуется для HTTPS через Nginx)
# -----------------------------------------------------------------------------
_csrf_origins_env = os.environ.get("CSRF_TRUSTED_ORIGINS", "")
if _csrf_origins_env:
    CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_origins_env.split(",") if o.strip()]
else:
    # Fallback: автоматически из ALLOWED_HOSTS
    CSRF_TRUSTED_ORIGINS = [f"https://{host}" for host in ALLOWED_HOSTS if host not in ["localhost", "127.0.0.1"]]


# -----------------------------------------------------------------------------
# CORS: в проде задаётся через env (и обычно только https домены)
# -----------------------------------------------------------------------------
raw_origins = os.environ.get("CORS_ALLOWED_ORIGINS", "")
CORS_ALLOWED_ORIGINS = [o.strip() for o in raw_origins.split(",") if o.strip()]


# -----------------------------------------------------------------------------
# Static Files: WhiteNoise для отдачи статики в production
# -----------------------------------------------------------------------------
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"


# -----------------------------------------------------------------------------
# Логи: по умолчанию в stdout (docker-friendly)
# -----------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "apps.ai": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "apps.ai_proxy": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
