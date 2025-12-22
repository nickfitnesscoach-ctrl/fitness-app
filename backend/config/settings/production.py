"""
Django production settings for FoodMind AI project.
"""

from .base import *  # noqa
import os


DEBUG = os.environ.get("DEBUG", "False") == "True"

# SECURITY: Disable Debug Mode in production by default
# This allows X-Debug-Mode header only if explicitly enabled in env
DEBUG_MODE_ENABLED = os.environ.get("DEBUG_MODE_ENABLED", "False") == "True"
WEBAPP_DEBUG_MODE_ENABLED = os.environ.get("DEBUG_MODE_ENABLED", "False") == "True"

# Hosts - load from environment
# SECURITY: Empty ALLOWED_HOSTS will cause Django to reject all requests
# This is intentional - production MUST have explicit allowed hosts
_allowed_hosts_env = os.environ.get("ALLOWED_HOSTS", "")
ALLOWED_HOSTS = [h.strip() for h in _allowed_hosts_env.split(",") if h.strip()]
if not ALLOWED_HOSTS:
    raise ValueError("ALLOWED_HOSTS environment variable must be set in production")

# PostgreSQL Database Configuration
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "foodmind"),
        "USER": os.getenv("POSTGRES_USER", "foodmind"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "supersecret"),
        "HOST": os.getenv("POSTGRES_HOST", "db"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 600,  # Connection pooling
    }
}

# Security settings for production
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "True") == "True"
CSRF_COOKIE_SECURE = os.environ.get("CSRF_COOKIE_SECURE", "True") == "True"

# Security Headers
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "False") == "True"

# CORS - prefer HTTPS origins in production
CORS_ALLOW_ALL_ORIGINS = False
raw_origins = os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")
CORS_ALLOWED_ORIGINS = [o.strip() for o in raw_origins if o.strip()]
CORS_ALLOW_CREDENTIALS = True

# Redis Cache Configuration for Production
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://redis:6379/1"),
        "KEY_PREFIX": "foodmind",
        "TIMEOUT": 300,  # Default timeout: 5 minutes
    }
}

# Structured logging configuration
# Docker best practice: logs to stdout by default
# Set DJANGO_LOG_TO_FILES=1 to write to /app/logs/ (requires volume mount)
USE_JSON_LOGGING = os.environ.get("USE_JSON_LOGGING", "True") == "True"
LOG_TO_FILES = os.environ.get("DJANGO_LOG_TO_FILES", "0") == "1"

# Build handlers list based on LOG_TO_FILES setting
_handlers = ["console"]
if LOG_TO_FILES:
    _handlers.append("file")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "json": {
            "()": "apps.common.logging.JSONFormatter",
        },
    },
    "handlers": {
        "file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": BASE_DIR / "logs" / "django.log",  # noqa: F405
            "maxBytes": 1024 * 1024 * 10,  # 10 MB
            "backupCount": 10,
            "formatter": "json" if USE_JSON_LOGGING else "verbose",
        },
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "json" if USE_JSON_LOGGING else "verbose",
        },
    },
    "root": {
        "handlers": _handlers,
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": _handlers,
            "level": "INFO",
            "propagate": False,
        },
        "apps.billing": {
            "handlers": _handlers,
            "level": "INFO",
            "propagate": False,
        },
        "apps.telegram": {
            "handlers": _handlers,
            "level": "DEBUG",
            "propagate": False,
        },
        "apps.ai": {
            "handlers": _handlers,
            "level": "INFO",
            "propagate": False,
        },
    },
}
