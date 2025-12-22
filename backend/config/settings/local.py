"""
local.py — настройки для разработки на своём компьютере.

Простыми словами:
- DEBUG включён (удобно смотреть ошибки)
- база может быть SQLite (самый простой старт)
- кэш в памяти (не нужен Redis)
- разрешаем localhost для фронта
"""

from __future__ import annotations

from . import base

# В локальной разработке мы явно включаем DEBUG
DEBUG = True

# Разрешённые хосты для локалки
ALLOWED_HOSTS = ["localhost", "127.0.0.1", ".ngrok-free.dev"]

# CORS: какие фронтенды могут делать запросы к API в dev
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]

# Cache: быстрый in-memory кэш (без Redis)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "eatfit24-local-cache",
        "OPTIONS": {"MAX_ENTRIES": 10000},
    }
}

# База данных: SQLite — самый простой вариант для dev
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": base.BASE_DIR / "db.sqlite3",
    }
}

# DRF: в dev можно включить Browsable API (удобно для дебага в браузере)
REST_FRAMEWORK = {**base.REST_FRAMEWORK}
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [
    "rest_framework.renderers.JSONRenderer",
    "rest_framework.renderers.BrowsableAPIRenderer",
]


# --- Всё остальное берём из base.py (без star import) ---
# Это явное “сцепление” настроек: Django читает module-level переменные.
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
