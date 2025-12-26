"""
base.py — общие настройки Django, которые используются и в локалке, и в проде.

Простыми словами:
- этот файл = “общая база”
- local.py / production.py / test.py берут этот файл и переопределяют то, что отличается

ВАЖНОЕ ПРАВИЛО:
- НИКАКИХ настроек, зависящих от окружения (типа Redis/LocMem cache) — здесь.
  Это задаётся в local.py / production.py / test.py, чтобы не было путаницы.
"""

from __future__ import annotations

from datetime import timedelta
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured  # noqa: F401

# BASE_DIR указывает на корень backend-проекта (где manage.py и т.д.)
BASE_DIR = Path(__file__).resolve().parent.parent.parent


# -----------------------------------------------------------------------------
# Безопасность: секретный ключ
# -----------------------------------------------------------------------------
# SECRET_KEY читается из окружения. Проверка на непустоту происходит позже,
# чтобы test.py мог переопределить его.
SECRET_KEY = os.environ.get("SECRET_KEY") or os.environ.get("DJANGO_SECRET_KEY") or ""


# -----------------------------------------------------------------------------
# DEBUG
# -----------------------------------------------------------------------------
# По умолчанию DEBUG выключен (безопаснее).
# В local.py он будет включаться явно.
DEBUG = os.environ.get("DEBUG", "False").lower() == "true"


# -----------------------------------------------------------------------------
# Hosts (какие домены имеют право обращаться к Django)
# -----------------------------------------------------------------------------
# В base держим максимально безопасный дефолт.
# В production.py будет строгая проверка, что ALLOWED_HOSTS не пустой.
ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if h.strip()
]


# -----------------------------------------------------------------------------
# Приложения
# -----------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",  # используется точечно (если нужно генерировать токены)
    "drf_spectacular",
    "django_filters",
    "corsheaders",
]

LOCAL_APPS = [
    "apps.core",
    "apps.users",
    "apps.nutrition",
    "apps.billing",
    "apps.ai",
    "apps.ai_proxy",
    "apps.common",
    "apps.telegram",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS


# -----------------------------------------------------------------------------
# Middleware
# -----------------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # Serve static files in production
    "corsheaders.middleware.CorsMiddleware",  # CORS должен быть высоко в списке
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Ограничение доступа к админке/ручкам Telegram (ваш кастомный middleware)
    "apps.telegram.telegram_auth.TelegramAdminOnlyMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"


# -----------------------------------------------------------------------------
# Templates
# -----------------------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]


# -----------------------------------------------------------------------------
# Database (общий дефолт = PostgreSQL)
# -----------------------------------------------------------------------------
# В local.py/test.py можно переопределить SQLite, если нужно.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "foodmind"),
        "USER": os.getenv("POSTGRES_USER", "foodmind"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "foodmind"),
        "HOST": os.getenv("POSTGRES_HOST", "db"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
    }
}


# -----------------------------------------------------------------------------
# Cache
# -----------------------------------------------------------------------------
# Здесь намеренно НЕ задаём cache backend.
# Причина: чтобы не было “двойных CACHES”, как у тебя раньше.
# См. local.py / production.py / test.py
CACHES = {}


# -----------------------------------------------------------------------------
# Internationalization
# -----------------------------------------------------------------------------
LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True


# -----------------------------------------------------------------------------
# Static / Media
# -----------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Если проект за прокси (nginx) — для корректной генерации ссылок
USE_X_FORWARDED_HOST = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# -----------------------------------------------------------------------------
# Django REST Framework
# -----------------------------------------------------------------------------
REST_FRAMEWORK = {
    # Аутентификация: сначала debug (только dev), потом Telegram WebApp
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.telegram.auth.authentication.DebugModeAuthentication",
        "apps.telegram.auth.authentication.TelegramWebAppAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # Throttling = антиспам-защита (не тарифные лимиты)
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    # ВАЖНО: имена scope должны совпадать с throttles.py в apps.ai
    "DEFAULT_THROTTLE_RATES": {
        "anon": "500/hour",
        "user": "5000/hour",
        # AI
        "ai_per_minute": "10/minute",
        "ai_per_day": "100/day",
        "task_status": "60/minute",  # scope для polling статуса задачи
        # Billing/Webhooks (если используешь)
        "webhook": "100/hour",
        "payment_creation": "20/hour",
    },
    # Единый формат ошибок для фронта
    "EXCEPTION_HANDLER": "apps.core.exception_handler.custom_exception_handler",
    "DATETIME_FORMAT": "%Y-%m-%dT%H:%M:%S%z",
    "DATE_FORMAT": "%Y-%m-%d",
    "TIME_FORMAT": "%H:%M:%S",
}


# -----------------------------------------------------------------------------
# OpenAPI (Swagger)
# -----------------------------------------------------------------------------
SPECTACULAR_SETTINGS = {
    "TITLE": "EatFit24 REST API",
    "DESCRIPTION": "REST API для EatFit24 (КБЖУ + распознавание по фото)",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api/v1/",
    "COMPONENT_SPLIT_REQUEST": True,
}


# -----------------------------------------------------------------------------
# CORS
# -----------------------------------------------------------------------------
# В base: максимально безопасно. В local.py разрешим localhost.
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()
]

CORS_ALLOW_METHODS = ["DELETE", "GET", "OPTIONS", "PATCH", "POST", "PUT"]
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    # Telegram WebApp auth
    "x-telegram-init-data",
    "x-telegram-id",
    "x-telegram-first-name",
    "x-telegram-last-name",
    "x-telegram-username",
    "x-telegram-language-code",
    # Debug mode (DEV only)
    "x-debug-mode",
    "x-debug-user-id",
]


# -----------------------------------------------------------------------------
# AI Proxy (внутренний сервис)
# -----------------------------------------------------------------------------
AI_PROXY_URL = os.environ.get("AI_PROXY_URL", "")
AI_PROXY_SECRET = os.environ.get("AI_PROXY_SECRET", "")


# -----------------------------------------------------------------------------
# Telegram Bot
# -----------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")


# -----------------------------------------------------------------------------
# Celery
# -----------------------------------------------------------------------------
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300  # 5 минут на задачу

CELERY_TASK_ROUTES = {
    "apps.ai.tasks.*": {"queue": "ai"},
    "apps.billing.tasks.*": {"queue": "billing"},
    "apps.billing.webhooks.tasks.*": {"queue": "billing"},
}

# ВАЖНО: чтобы не было случайного “sync AI” в проде — включаем async по умолчанию.
AI_ASYNC_ENABLED = os.environ.get("AI_ASYNC_ENABLED", "True").lower() == "true"


# -----------------------------------------------------------------------------
# Billing: Recurring Payments (Auto-renew)
# -----------------------------------------------------------------------------
# Feature flag для автопродления подписок.
# Включить только после полного тестирования!
BILLING_RECURRING_ENABLED = os.environ.get("BILLING_RECURRING_ENABLED", "False").lower() == "true"


# -----------------------------------------------------------------------------
# JWT (если нужно)
# -----------------------------------------------------------------------------
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# Явно перечисляем, что можно импортировать из base.py в local/production/test.
# Это убирает "магические" зависимости и помогает линтерам (Ruff).
__all__ = [
    "BASE_DIR",
    "SECRET_KEY",
    "DEBUG",
    "ALLOWED_HOSTS",
    "INSTALLED_APPS",
    "MIDDLEWARE",
    "ROOT_URLCONF",
    "WSGI_APPLICATION",
    "TEMPLATES",
    "DATABASES",
    "CACHES",
    "REST_FRAMEWORK",
    "LANGUAGE_CODE",
    "TIME_ZONE",
    "USE_I18N",
    "USE_TZ",
    "STATIC_URL",
    "STATIC_ROOT",
    "MEDIA_URL",
    "MEDIA_ROOT",
    "DEFAULT_AUTO_FIELD",
    "SPECTACULAR_SETTINGS",
    "CORS_ALLOW_ALL_ORIGINS",
    "CORS_ALLOWED_ORIGINS",
    "CORS_ALLOW_CREDENTIALS",
    "CORS_ALLOW_METHODS",
    "CORS_ALLOW_HEADERS",
    "AI_PROXY_URL",
    "AI_PROXY_SECRET",
    "AI_ASYNC_ENABLED",
    "TELEGRAM_BOT_TOKEN",
    "CELERY_BROKER_URL",
    "CELERY_RESULT_BACKEND",
    "CELERY_ACCEPT_CONTENT",
    "CELERY_TASK_SERIALIZER",
    "CELERY_RESULT_SERIALIZER",
    "CELERY_TIMEZONE",
    "CELERY_TASK_TRACK_STARTED",
    "CELERY_TASK_TIME_LIMIT",
    "CELERY_TASK_ROUTES",
    "SIMPLE_JWT",
]
