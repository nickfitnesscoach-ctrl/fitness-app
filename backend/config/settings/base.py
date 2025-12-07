"""
Django base settings for FoodMind AI project.
Common settings for all environments.
"""

from datetime import datetime, timedelta, timezone as dt_timezone
import os
from pathlib import Path

from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load environment variables from .env file
load_dotenv(BASE_DIR / '.env')


# SECURITY WARNING: keep the secret key used in production secret!
# Require SECRET_KEY in production - no insecure defaults

SECRET_KEY = os.environ.get("SECRET_KEY") or os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    # Allow default only in development
    DEBUG_MODE = os.environ.get("DEBUG", "True") == "True"
    if not DEBUG_MODE:
        raise ImproperlyConfigured(
            "SECRET_KEY environment variable must be set in production. "
            "Generate a secure key with: python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'"
        )
    # Development fallback (only when DEBUG=True)
    SECRET_KEY = "django-insecure-dev-only-c2+=p2+n2v)6cpyh2)#!reeaeni&73uk580gl)%$cp*m%()3&z"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get("DEBUG", "True") == "True" or os.environ.get("DJANGO_DEBUG", "True") == "True"

ALLOWED_HOSTS_RAW = os.environ.get("ALLOWED_HOSTS") or os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
ALLOWED_HOSTS = ALLOWED_HOSTS_RAW.split(",")


# Application definition

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
    "rest_framework_simplejwt",
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


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",  # CORS должен быть высоко в списке
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.telegram.telegram_auth.TelegramAdminOnlyMiddleware",  # After AuthenticationMiddleware so request.user exists
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

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
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

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


# ============================================================
# Cache Configuration
# ============================================================

# Use local memory cache for development (thread-safe)
# For production, use Redis or Memcached
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "foodmind-cache",
        "OPTIONS": {
            "MAX_ENTRIES": 10000,  # Maximum number of cache entries
        },
    }
}

# Production Redis cache configuration (uncomment for production):
# CACHES = {
#     "default": {
#         "BACKEND": "django.core.cache.backends.redis.RedisCache",
#         "LOCATION": os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/1"),
#         "OPTIONS": {
#             "CLIENT_CLASS": "django_redis.client.DefaultClient",
#         },
#         "KEY_PREFIX": "foodmind",
#         "TIMEOUT": 300,  # Default timeout: 5 minutes
#     }
# }


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {
            "min_length": 8,
        },
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = "ru-ru"

TIME_ZONE = "Europe/Moscow"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Media files (User uploads)
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Trust X-Forwarded-Host header from proxy (for correct URL generation in Docker)
USE_X_FORWARDED_HOST = True


# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ============================================================
# 4.5: Cache Configuration (Redis for API response caching)
# ============================================================

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/1")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "KEY_PREFIX": "eatfit24",
        "TIMEOUT": 300,  # 5 minutes default
    }
}


# ============================================================
# Django REST Framework Configuration
# ============================================================

REST_FRAMEWORK = {
    # Authentication
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.telegram.authentication.TelegramHeaderAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],

    # Permissions
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],

    # Pagination
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,

    # Filtering
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],

    # Rendering
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],

    # Parsing
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ],

    # Schema generation
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",

    # Throttling (rate limiting)
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/day",
        "user": "1000/day",
        "ai_per_minute": "10/minute",  # AI recognition rate limit
        "ai_per_day": "100/day",  # AI recognition rate limit
        "webhook": "100/hour",  # Webhook rate limit (YooKassa)
        "payment_creation": "20/hour",  # Payment creation rate limit
        "task_status": "60/minute",  # B-004 FIX: Task status polling rate limit
    },

    # Error handling
    "EXCEPTION_HANDLER": "rest_framework.views.exception_handler",

    # Date/Time formatting
    "DATETIME_FORMAT": "%Y-%m-%dT%H:%M:%S%z",
    "DATE_FORMAT": "%Y-%m-%d",
    "TIME_FORMAT": "%H:%M:%S",
}


# ============================================================
# JWT Authentication Configuration
# ============================================================

SIMPLE_JWT = {
    # Token lifetimes
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),

    # Rotation
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,

    # Algorithm
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,

    # Token claims
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",

    # Token classes
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",

    # Sliding tokens
    "SLIDING_TOKEN_REFRESH_EXP_CLAIM": "refresh_exp",
    "SLIDING_TOKEN_LIFETIME": timedelta(minutes=60),
    "SLIDING_TOKEN_REFRESH_LIFETIME": timedelta(days=7),
}


# ============================================================
# drf-spectacular (OpenAPI/Swagger) Configuration
# ============================================================

SPECTACULAR_SETTINGS = {
    "TITLE": "FoodMind AI REST API",
    "DESCRIPTION": "REST API для приложения автоматического подсчёта калорий (КБЖУ) с распознаванием блюд по фото",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,

    # API versioning
    "SCHEMA_PATH_PREFIX": r"/api/v1/",

    # Authentication
    "SECURITY": [{"bearerAuth": []}],
    "COMPONENTS": {
        "securitySchemes": {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        }
    },

    # Schema generation
    "COMPONENT_SPLIT_REQUEST": True,
    "SORT_OPERATIONS": False,
}


# ============================================================
# CORS Configuration
# ============================================================

# SECURITY: Never allow all origins
CORS_ALLOW_ALL_ORIGINS = False

# Load allowed origins from environment
raw_origins = os.environ.get(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://127.0.0.1:3000,http://127.0.0.1:5173"
).split(",")

# Validate and filter CORS origins
def validate_cors_origins(origins, debug_mode=DEBUG):
    """
    Validate CORS origins for security.

    - In production: Only allow HTTPS origins
    - In development: Allow HTTP for localhost/127.0.0.1
    - Always validate URL format
    - Log invalid origins
    """
    import logging
    from urllib.parse import urlparse

    logger = logging.getLogger(__name__)
    validated_origins = []

    for origin in origins:
        origin = origin.strip()
        if not origin:
            continue

        try:
            parsed = urlparse(origin)

            # Validate scheme
            if not parsed.scheme:
                logger.warning(f"CORS origin missing scheme: {origin}")
                continue

            # In production, only allow HTTPS
            if not debug_mode:
                if parsed.scheme != 'https':
                    logger.error(
                        f"SECURITY: HTTP origin not allowed in production: {origin}. "
                        "Only HTTPS origins are permitted."
                    )
                    continue
            else:
                # In development, allow HTTP only for localhost/127.0.0.1
                if parsed.scheme == 'http':
                    hostname = parsed.hostname
                    if hostname not in ['localhost', '127.0.0.1', '::1']:
                        logger.warning(
                            f"HTTP origin allowed only for localhost in development: {origin}"
                        )
                        continue

            # Validate hostname
            if not parsed.hostname:
                logger.warning(f"CORS origin missing hostname: {origin}")
                continue

            # No wildcards allowed
            if '*' in origin:
                logger.error(f"SECURITY: Wildcards not allowed in CORS origins: {origin}")
                continue

            validated_origins.append(origin)

        except Exception as e:
            logger.error(f"Invalid CORS origin format '{origin}': {e}")
            continue

    # Validate CORS configuration in production
    if not validated_origins:
        if debug_mode:
            logger.warning(
                "No CORS_ALLOWED_ORIGINS configured. This is OK for development, "
                "but you must set it in production if using a web frontend."
            )
        else:
            logger.warning(
                "No CORS_ALLOWED_ORIGINS configured in production. "
                "If you're using a web frontend, set CORS_ALLOWED_ORIGINS environment variable."
            )

    return validated_origins

# Apply validation
CORS_ALLOWED_ORIGINS = validate_cors_origins(raw_origins, DEBUG)

# Allow credentials (required for JWT authentication)
CORS_ALLOW_CREDENTIALS = True

# Don't use regex patterns for security
CORS_ALLOWED_ORIGIN_REGEXES = []

# Allowed HTTP methods (RESTful API standard)
CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]

# Allowed headers (strict whitelist)
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
    "x-telegram-init-data",  # Telegram Mini App authentication (initData)
    "x-telegram-id",  # Telegram user ID from Nginx proxy
    "x-telegram-first-name",  # Telegram user first name
    "x-telegram-username",  # Telegram username
    "x-telegram-last-name",  # Telegram user last name
    "x-telegram-language-code",  # Telegram user language
]

# Security: Don't expose sensitive headers
CORS_EXPOSE_HEADERS = []

# Cache preflight requests for 1 hour
CORS_PREFLIGHT_MAX_AGE = 3600


# ============================================================
# OpenRouter AI Configuration
# ============================================================

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_SITE_URL = os.environ.get("OPENROUTER_SITE_URL", "http://localhost:8000")
OPENROUTER_SITE_NAME = os.environ.get("OPENROUTER_SITE_NAME", "FoodMind AI")
# Changed from openai/gpt-5-image-mini due to geographic restrictions (403 error in Russia)
# Changed from google/gemini-2.0-flash-exp:free due to rate limiting on free tier
# Changed from anthropic/claude-3.5-haiku - Bedrock version doesn't support vision
# Google Gemini 2.5 Flash Image (Nano Banana) - stable, cheap ($0.30/M), good vision
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "google/gemini-2.5-flash-image")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# AI Recognition Settings
AI_MAX_RETRIES = 3  # Maximum retries for invalid JSON
AI_RATE_LIMIT_PER_MINUTE = 10  # Requests per minute per IP
AI_RATE_LIMIT_PER_DAY = 100  # Requests per day per IP

# ============================================================
# AI Proxy Configuration (EatFit24 Internal Service)
# ============================================================
# AI Proxy is an internal service that wraps OpenRouter API calls
# Accessible only via Tailscale VPN
AI_PROXY_URL = os.environ.get("AI_PROXY_URL", "")
AI_PROXY_SECRET = os.environ.get("AI_PROXY_SECRET", "")


# ============================================================
# Email Configuration
# ============================================================

EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend"  # Console backend for development
)

# SMTP Settings (for production)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True") == "True"
EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL", "False") == "True"
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")

# Default sender email
DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL",
    "FoodMind AI <noreply@foodmind.ai>"
)
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# Email verification settings
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")
API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")


# ============================================================
# YooKassa Payment Configuration
# ============================================================

# YooKassa mode: test or prod
YOOKASSA_MODE = os.environ.get("YOOKASSA_MODE", "test")

# Test credentials
YOOKASSA_SHOP_ID_TEST = os.environ.get("YOOKASSA_SHOP_ID_TEST", "")
YOOKASSA_API_KEY_TEST = os.environ.get("YOOKASSA_API_KEY_TEST", "")

# Production credentials
YOOKASSA_SHOP_ID_PROD = os.environ.get("YOOKASSA_SHOP_ID_PROD", "")
YOOKASSA_API_KEY_PROD = os.environ.get("YOOKASSA_API_KEY_PROD", "")

# Active credentials based on mode
if YOOKASSA_MODE == "prod":
    YOOKASSA_SHOP_ID = YOOKASSA_SHOP_ID_PROD
    YOOKASSA_SECRET_KEY = YOOKASSA_API_KEY_PROD
else:
    YOOKASSA_SHOP_ID = YOOKASSA_SHOP_ID_TEST
    YOOKASSA_SECRET_KEY = YOOKASSA_API_KEY_TEST

# Return URL for payment confirmation
YOOKASSA_RETURN_URL = os.environ.get("YOOKASSA_RETURN_URL", "https://eatfit24.ru/payments/return/")

# Webhook secret for signature validation (optional)
YOOKASSA_WEBHOOK_SECRET = os.environ.get("YOOKASSA_WEBHOOK_SECRET", "")

# Billing constants
BILLING_PLUS_PLAN_CODE = "PLUS"
BILLING_PLUS_DURATION_DAYS = 30


# ============================================================
# Telegram Bot Configuration
# ============================================================

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_BOT_USERNAME = os.environ.get("TELEGRAM_BOT_USERNAME", "EatFit24_bot")

# Дополнительный админ из окружения (совместимость с ботом)
BOT_ADMIN_ID = os.environ.get("BOT_ADMIN_ID")

# Telegram admin IDs (comma-separated in env)
_telegram_admins_str = os.environ.get("TELEGRAM_ADMINS", "")
TELEGRAM_ADMINS = set(int(x.strip()) for x in _telegram_admins_str.split(",") if x.strip().isdigit())
if BOT_ADMIN_ID and BOT_ADMIN_ID.isdigit():
    TELEGRAM_ADMINS.add(int(BOT_ADMIN_ID))


# ============================================================
# Subscription Settings
# ============================================================

# FREE subscription configuration

FREE_SUBSCRIPTION_END_DATE = datetime(2099, 12, 31, 23, 59, 59, tzinfo=dt_timezone.utc)

# File upload limits
MAX_UPLOAD_SIZE_MB = 10  # Maximum file size for photo uploads
MAX_IMAGE_DIMENSION = 4096  # Maximum width/height for images (4K)


# ============================================================
# Celery Configuration
# ============================================================

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300  # 5 minutes max per task

# Task routes - separate queues for different task types
CELERY_TASK_ROUTES = {
    "apps.ai.tasks.*": {"queue": "ai"},
    "apps.billing.tasks.*": {"queue": "billing"},
}

# Enable async AI processing (set to False to use sync mode)
AI_ASYNC_ENABLED = os.environ.get("AI_ASYNC_ENABLED", "False") == "True"
