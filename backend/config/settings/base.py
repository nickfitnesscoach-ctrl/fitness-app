"""
config/settings/base.py

Общие настройки Django (нейтральные по окружению).

Ключевой принцип:
- base.py не должен "угадывать" окружение.
- Всё окружение определяется через APP_ENV и конкретные settings-файлы (local/production/test).
"""

from __future__ import annotations

from datetime import timedelta
import os
from pathlib import Path
from typing import List

# BASE_DIR указывает на корень backend-проекта (где manage.py и т.д.)
BASE_DIR = Path(__file__).resolve().parent.parent.parent


# =============================================================================
# ENV / РЕЖИМ ОКРУЖЕНИЯ
# =============================================================================

APP_ENV = (
    os.environ.get("APP_ENV", "").strip().lower()
)  # dev|prod|test (пусто = ошибка конфигурации)
DEBUG = os.environ.get("DEBUG", "False").lower() == "true"


# =============================================================================
# Безопасность: SECRET_KEY
# =============================================================================

SECRET_KEY = os.environ.get("SECRET_KEY") or os.environ.get("DJANGO_SECRET_KEY") or ""

# CRITICAL: Fail-fast if SECRET_KEY is empty in production
# This must happen BEFORE any imports that use SECRET_KEY (e.g., rest_framework_simplejwt)
if not SECRET_KEY and os.environ.get("DJANGO_SETTINGS_MODULE", "").endswith("production"):
    raise RuntimeError(
        "[SAFETY] SECRET_KEY must be set before loading production settings. "
        "Add SECRET_KEY=... to .env file."
    )


# =============================================================================
# Hosts
# =============================================================================

ALLOWED_HOSTS: List[str] = [
    h.strip()
    for h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if h.strip()
]


# =============================================================================
# Apps
# =============================================================================

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
    # "rest_framework_simplejwt",  # REMOVED: causes SECRET_KEY import before settings are loaded
    # "rest_framework_simplejwt.token_blacklist",  # Also removed - imports models.py which needs SECRET_KEY
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


# =============================================================================
# Middleware
# =============================================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Ограничение доступа к /dj-admin/* и админским ручкам (Telegram admin)
    "apps.telegram.telegram_auth.TelegramAdminOnlyMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"


# =============================================================================
# Templates
# =============================================================================

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


# =============================================================================
# Database / Cache
# =============================================================================
# base.py не должен задавать реальные окруженческие значения.
# Окружение обязано настроить DATABASES и CACHES в local.py / production.py / test.py.
DATABASES = {}
CACHES = {}


# =============================================================================
# I18N
# =============================================================================

LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True


# =============================================================================
# Static / Media
# =============================================================================

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

USE_X_FORWARDED_HOST = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# =============================================================================
# DRF
# =============================================================================

REST_FRAMEWORK = {
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
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "500/hour",
        "user": "5000/hour",
        "ai_per_minute": "10/minute",
        "ai_per_day": "100/day",
        "task_status": "60/minute",
        "webhook": "100/hour",
        "billing_create_payment": "20/hour",
        "billing_polling": "120/min",
    },
    "EXCEPTION_HANDLER": "apps.core.exception_handler.custom_exception_handler",
    "DATETIME_FORMAT": "%Y-%m-%dT%H:%M:%S%z",
    "DATE_FORMAT": "%Y-%m-%d",
    "TIME_FORMAT": "%H:%M:%S",
}


# =============================================================================
# OpenAPI
# =============================================================================

SPECTACULAR_SETTINGS = {
    "TITLE": "EatFit24 REST API",
    "DESCRIPTION": "REST API для EatFit24 (КБЖУ + распознавание по фото)",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api/v1/",
    "COMPONENT_SPLIT_REQUEST": True,
}


# =============================================================================
# CORS
# =============================================================================

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()
]

CORS_ALLOW_METHODS = ["DELETE", "GET", "OPTIONS", "PATCH", "POST", "PUT"]

# Важно: заголовки Telegram для initData.
# Никогда не доверяем X-Telegram-Id и прочим, если нет валидного initData.
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
    "x-telegram-init-data",
    # Debug mode (DEV only)
    "x-debug-mode",
    "x-debug-user-id",
    "x-telegram-first-name",
    "x-telegram-last-name",
    "x-telegram-username",
    "x-telegram-language-code",
]


# =============================================================================
# Trusted Proxies (audit / ip)
# =============================================================================

TRUSTED_PROXIES_ENABLED = os.environ.get("TRUSTED_PROXIES_ENABLED", "false").lower() == "true"
TRUSTED_PROXIES = [p.strip() for p in os.environ.get("TRUSTED_PROXIES", "").split(",") if p.strip()]


# =============================================================================
# AI Proxy
# =============================================================================

AI_PROXY_URL = os.environ.get("AI_PROXY_URL", "")
AI_PROXY_SECRET = os.environ.get("AI_PROXY_SECRET", "")
AI_ASYNC_ENABLED = os.environ.get("AI_ASYNC_ENABLED", "True").lower() == "true"


# =============================================================================
# Telegram settings (без парсинга "магией")
# =============================================================================

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_BOT_API_SECRET = os.environ.get("TELEGRAM_BOT_API_SECRET", "")


def _env_int_list(name: str) -> list[int]:
    raw = os.environ.get(name, "")
    if not raw.strip():
        return []
    out: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(int(part))
        except ValueError:
            raise RuntimeError(f"[SAFETY] {name} must be comma-separated integers, got: {part!r}")
    return out


TELEGRAM_ADMINS: list[int] = _env_int_list("TELEGRAM_ADMINS")


# =============================================================================
# Celery (только базовые значения, маршрутизация — в celery.py)
# =============================================================================

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300
CELERY_TASK_ROUTES = {}  # задаётся в config/celery.py


# =============================================================================
# Billing
# =============================================================================

BILLING_RECURRING_ENABLED = os.environ.get("BILLING_RECURRING_ENABLED", "False").lower() == "true"

YOOKASSA_SHOP_ID = os.environ.get("YOOKASSA_SHOP_ID", "")
YOOKASSA_SECRET_KEY = os.environ.get("YOOKASSA_SECRET_KEY", "")
YOOKASSA_MODE = os.environ.get("YOOKASSA_MODE", "")
YOOKASSA_RETURN_URL = os.environ.get("YOOKASSA_RETURN_URL", "")
YOOKASSA_WEBHOOK_URL = os.environ.get("YOOKASSA_WEBHOOK_URL", "")
YOOKASSA_WEBHOOK_VERIFY_SIGNATURE = (
    os.environ.get("YOOKASSA_WEBHOOK_VERIFY_SIGNATURE", "true").lower() == "true"
)


# =============================================================================
# JWT
# =============================================================================

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    # SIGNING_KEY intentionally omitted - SimpleJWT will use settings.SECRET_KEY automatically
    # This prevents early access to SECRET_KEY during settings import
    "AUTH_HEADER_TYPES": ("Bearer",),
}
