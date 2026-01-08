"""
config/settings/local.py — настройки для локальной разработки (DEV).

Цели этого файла:
1) Удобная разработка на своём ПК: DEBUG, подробные ошибки, Browsable API.
2) Два режима базы данных:
   - По умолчанию: PostgreSQL (как в docker-compose) — ближе к продакшену.
   - Опционально: SQLite (без Docker) — самый быстрый старт.
3) Кэш:
   - По умолчанию: Redis (если он поднят) — ближе к продакшену.
   - Опционально: In-memory кэш (LocMem) — если Redis не нужен.
4) Безопасные дефолты:
   - Не требуем продовых доменов
   - Явно перечисляем localhost/127.0.0.1/backend
   - Секреты читаем из env, без утечек в git
"""

from __future__ import annotations

import os
from typing import List

from . import base


# =============================================================================
# 0) Маленькие хелперы для env
# =============================================================================

def _env(name: str, default: str | None = None) -> str | None:
    """Простой доступ к переменной окружения."""
    return os.environ.get(name, default)


def _env_bool(name: str, default: bool = False) -> bool:
    """Boolean из env: '1/true/yes/on' -> True."""
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on", "y"}


def _env_list(name: str, default_csv: str) -> List[str]:
    """
    Список из env через запятую.
    Пустые элементы удаляем, пробелы режем.
    """
    raw = os.environ.get(name, default_csv)
    return [x.strip() for x in raw.split(",") if x.strip()]


# =============================================================================
# 1) Базовые DEV настройки
# =============================================================================

# В DEV всегда включаем debug.
DEBUG = True

# Вебапп debug-флаг (поддержка X-Debug-Mode / debug пользователя на фронте).
# Важно: этот флаг имеет смысл только в local/dev окружении.
WEBAPP_DEBUG_MODE_ENABLED = _env_bool("WEBAPP_DEBUG_MODE_ENABLED", True)

# SECRET_KEY:
# - В local/dev допускаем простой ключ из env или дефолт
# - В проде ключ должен быть строго из env (это делается в production.py)
SECRET_KEY = (
    _env("SECRET_KEY")
    or _env("DJANGO_SECRET_KEY")
    or "local-dev-secret-key-change-me"
)

# ALLOWED_HOSTS:
# В dev разрешаем стандартные хосты, которые реально встречаются:
# - localhost/127.0.0.1: локальная машина
# - backend/db/redis: имена docker-сервисов внутри сети
# - 0.0.0.0: когда runserver слушает на всех интерфейсах
# - .ngrok-free.dev: если иногда пробрасываешь webhook через ngrok
ALLOWED_HOSTS = _env_list(
    "ALLOWED_HOSTS",
    "localhost,127.0.0.1,0.0.0.0,backend,db,redis,.ngrok-free.dev",
)

# CSRF_TRUSTED_ORIGINS:
# Для dev обычно хватает localhost фронта.
# Если используешь другой порт — добавь сюда через env.
CSRF_TRUSTED_ORIGINS = _env_list(
    "CSRF_TRUSTED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000",
)

# CORS:
# В dev фронт обычно ходит с localhost:5173 (Vite) или 3000.
# Важно: если используешь cookies/credentials — нужно CORS_ALLOW_CREDENTIALS=True (см. base).
CORS_ALLOWED_ORIGINS = _env_list(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
)

# =============================================================================
# 2) База данных (Postgres по умолчанию, SQLite опционально)
# =============================================================================

# Переключатель: USE_SQLITE=1 -> SQLite без Docker.
USE_SQLITE = _env_bool("USE_SQLITE", False)

if USE_SQLITE:
    # Быстрый старт без Docker: sqlite файл рядом с проектом
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": base.BASE_DIR / "db.sqlite3",
        }
    }
else:
    # Режим "как в Docker": PostgreSQL
    # Важно: пароль/имя БД берём из env (из .env/.env.local через compose).
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": _env("POSTGRES_DB", "eatfit24"),
            "USER": _env("POSTGRES_USER", "eatfit24"),
            "PASSWORD": _env("POSTGRES_PASSWORD", ""),
            "HOST": _env("POSTGRES_HOST", "db"),
            "PORT": _env("POSTGRES_PORT", "5432"),
            # Удобно в dev: каждая HTTP-запрос-операция в транзакции.
            # Минус: может скрывать проблемы с долгими транзакциями.
            "ATOMIC_REQUESTS": True,
        }
    }


# =============================================================================
# 3) Кэш (Redis по умолчанию, LocMem опционально)
# =============================================================================

# Переключатель: USE_REDIS_CACHE=0 -> LocMemCache.
# В docker-dev Redis обычно есть — оставляем Redis как дефолт.
USE_REDIS_CACHE = _env_bool("USE_REDIS_CACHE", True)

if USE_REDIS_CACHE:
    # Если base уже настраивает redis cache — можно ничего не переопределять.
    # Но оставим явную dev-настройку: читаем REDIS_URL из env, иначе дефолт.
    REDIS_URL = _env("REDIS_URL", "redis://redis:6379/0")
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }
else:
    # In-memory кэш (не требует Redis)
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "eatfit24-local-cache",
            "OPTIONS": {"MAX_ENTRIES": 10000},
        }
    }


# =============================================================================
# 4) DRF: включаем Browsable API для удобства разработки
# =============================================================================

REST_FRAMEWORK = {**base.REST_FRAMEWORK}
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [
    "rest_framework.renderers.JSONRenderer",
    "rest_framework.renderers.BrowsableAPIRenderer",
]


# =============================================================================
# 5) Всё остальное наследуем из base.py
# =============================================================================
# Важно: мы НЕ делаем `from .base import *`, чтобы:
# - не терять контроль над тем, что переопределено
# - было проще читать диффы и искать настройки

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

# CORS базовые настройки (методы/хедеры/credentials) — берём из base
CORS_ALLOW_ALL_ORIGINS = base.CORS_ALLOW_ALL_ORIGINS
CORS_ALLOW_CREDENTIALS = base.CORS_ALLOW_CREDENTIALS
CORS_ALLOW_METHODS = base.CORS_ALLOW_METHODS
CORS_ALLOW_HEADERS = base.CORS_ALLOW_HEADERS

# AI / Proxy настройки — берём из base (там читаются из env)
AI_PROXY_URL = base.AI_PROXY_URL
AI_PROXY_SECRET = base.AI_PROXY_SECRET
AI_ASYNC_ENABLED = base.AI_ASYNC_ENABLED

# Celery настройки — берём из base (там читаются из env)
CELERY_BROKER_URL = base.CELERY_BROKER_URL
CELERY_RESULT_BACKEND = base.CELERY_RESULT_BACKEND
CELERY_ACCEPT_CONTENT = base.CELERY_ACCEPT_CONTENT
CELERY_TASK_SERIALIZER = base.CELERY_TASK_SERIALIZER
CELERY_RESULT_SERIALIZER = base.CELERY_RESULT_SERIALIZER
CELERY_TIMEZONE = base.CELERY_TIMEZONE
CELERY_TASK_TRACK_STARTED = base.CELERY_TASK_TRACK_STARTED
CELERY_TASK_TIME_LIMIT = base.CELERY_TASK_TIME_LIMIT
CELERY_TASK_ROUTES = base.CELERY_TASK_ROUTES

# JWT настройки — берём из base
SIMPLE_JWT = base.SIMPLE_JWT
