"""
config/settings/local.py — настройки DEV.

Цели:
- удобная локальная разработка
- безопасные дефолты (dev-имена БД)
- fail-fast, чтобы не ловить "тихий 401" и не подключиться к прод-ресурсам
"""

from __future__ import annotations

import logging
import os
from typing import List

from . import base

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Хелперы
# -----------------------------------------------------------------------------


def _env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on", "y"}


def _env_list(name: str, default_csv: str) -> List[str]:
    raw = os.environ.get(name, default_csv)
    return [x.strip() for x in raw.split(",") if x.strip()]


def _required(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        raise RuntimeError(f"[SAFETY] Missing required env var: {name}")
    return val


# -----------------------------------------------------------------------------
# ENV guard
# -----------------------------------------------------------------------------

APP_ENV = (_env("APP_ENV", "dev") or "dev").strip().lower()
if APP_ENV == "prod":
    raise RuntimeError("[SAFETY] APP_ENV=prod but local.py is loaded. This is misconfiguration.")

DEBUG = True
WEBAPP_DEBUG_MODE_ENABLED = _env_bool("WEBAPP_DEBUG_MODE_ENABLED", True)

SECRET_KEY = _env("SECRET_KEY") or _env("DJANGO_SECRET_KEY") or "local-dev-secret-key-change-me"

ALLOWED_HOSTS = _env_list(
    "ALLOWED_HOSTS",
    "localhost,127.0.0.1,0.0.0.0,backend,db,redis,.ngrok-free.dev",
)

CSRF_TRUSTED_ORIGINS = _env_list(
    "CSRF_TRUSTED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
)

CORS_ALLOWED_ORIGINS = _env_list(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
)

# -----------------------------------------------------------------------------
# DB: dev безопасные дефолты
# -----------------------------------------------------------------------------

USE_SQLITE = _env_bool("USE_SQLITE", False)

if USE_SQLITE:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": base.BASE_DIR / "db.sqlite3",
        }
    }
else:
    db_name = (_env("POSTGRES_DB", "eatfit24_dev") or "eatfit24_dev").strip()
    db_user = (_env("POSTGRES_USER", "eatfit24_dev") or "eatfit24_dev").strip()

    # Жёстко запрещаем "подозрительные" имена (кроме CI)
    # В CI разрешаем дефолтное имя "eatfit24" для обратной совместимости
    is_ci = os.environ.get("CI") == "true" or os.environ.get("GITHUB_ACTIONS") == "true"
    forbidden = {"eatfit24_prod", "foodmind", "foodmind_prod"}
    if not is_ci:
        forbidden.add("eatfit24")  # В локальной разработке требуем явно eatfit24_dev

    if db_name in forbidden or db_name.endswith("_prod") or "_prod" in db_name:
        raise RuntimeError(f"[SAFETY] Forbidden DB name for DEV: {db_name!r}. Use eatfit24_dev.")

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": db_name,
            "USER": db_user,
            "PASSWORD": _env("POSTGRES_PASSWORD", ""),
            "HOST": _env("POSTGRES_HOST", "db"),
            "PORT": _env("POSTGRES_PORT", "5432"),
            "ATOMIC_REQUESTS": True,
        }
    }

# -----------------------------------------------------------------------------
# Cache: Redis в dev по умолчанию (с prefix)
# -----------------------------------------------------------------------------

USE_REDIS_CACHE = _env_bool("USE_REDIS_CACHE", True)

if USE_REDIS_CACHE:
    REDIS_URL = _env("REDIS_URL", "redis://redis:6379/0")
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
            "KEY_PREFIX": "eatfit24_dev",
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "eatfit24-local-cache",
            "OPTIONS": {"MAX_ENTRIES": 10000},
        }
    }

# -----------------------------------------------------------------------------
# Telegram: в dev токен обязателен (иначе будет тихий 401)
# -----------------------------------------------------------------------------

TELEGRAM_BOT_TOKEN = base.TELEGRAM_BOT_TOKEN
TELEGRAM_ADMINS = base.TELEGRAM_ADMINS

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError(
        "[SAFETY] TELEGRAM_BOT_TOKEN is empty in DEV. "
        "WebApp auth / trainer panel will fail. Set it in .env.local"
    )

# В dev админы могут быть пустыми, но тогда панель заблокирована — лучше явно знать.
if not TELEGRAM_ADMINS:
    logger.warning("[DEV] TELEGRAM_ADMINS is empty. Trainer panel will be denied.")

# -----------------------------------------------------------------------------
# Billing: в dev запрещаем live ключи
# -----------------------------------------------------------------------------

if base.YOOKASSA_SECRET_KEY.startswith("live_"):
    raise RuntimeError("[SAFETY] live_ YooKassa key detected in DEV. Use test_ keys only.")

# -----------------------------------------------------------------------------
# DRF: включаем Browsable API
# -----------------------------------------------------------------------------

REST_FRAMEWORK = {**base.REST_FRAMEWORK}
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [
    "rest_framework.renderers.JSONRenderer",
    "rest_framework.renderers.BrowsableAPIRenderer",
]

# -----------------------------------------------------------------------------
# Наследование из base.py
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

STATIC_URL = base.STATIC_URL
STATIC_ROOT = base.STATIC_ROOT
MEDIA_URL = base.MEDIA_URL
MEDIA_ROOT = base.MEDIA_ROOT

DEFAULT_AUTO_FIELD = base.DEFAULT_AUTO_FIELD
SPECTACULAR_SETTINGS = base.SPECTACULAR_SETTINGS

CORS_ALLOW_ALL_ORIGINS = base.CORS_ALLOW_ALL_ORIGINS
CORS_ALLOW_CREDENTIALS = base.CORS_ALLOW_CREDENTIALS
CORS_ALLOW_METHODS = base.CORS_ALLOW_METHODS
CORS_ALLOW_HEADERS = base.CORS_ALLOW_HEADERS

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

SIMPLE_JWT = base.SIMPLE_JWT

YOOKASSA_SHOP_ID = base.YOOKASSA_SHOP_ID
YOOKASSA_SECRET_KEY = base.YOOKASSA_SECRET_KEY
YOOKASSA_MODE = base.YOOKASSA_MODE
YOOKASSA_RETURN_URL = base.YOOKASSA_RETURN_URL
YOOKASSA_WEBHOOK_URL = base.YOOKASSA_WEBHOOK_URL
YOOKASSA_WEBHOOK_VERIFY_SIGNATURE = base.YOOKASSA_WEBHOOK_VERIFY_SIGNATURE

logger.info("[DEV SETTINGS] loaded. APP_ENV=%s DB=%s", APP_ENV, DATABASES["default"]["NAME"])
