"""
test.py — настройки для автотестов.

Простыми словами:
- тестам не нужен PostgreSQL/Redis
- делаем всё максимально быстро: SQLite in-memory + простой cache
"""

from __future__ import annotations

from .base import *  # noqa

# Override SECRET_KEY for tests (base.py now allows empty value)
SECRET_KEY = "test-secret-key-for-pytest-only-do-not-use-in-prod"  # noqa: F811

DEBUG = False

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "eatfit24-test-cache",
    }
}

# Быстрый хешер паролей для тестов
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Логи в тестах обычно мешают — выключаем
LOGGING = {"version": 1, "disable_existing_loggers": True}
