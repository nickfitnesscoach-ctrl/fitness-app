"""
Django development (local) settings for FoodMind AI project.
"""

from .base import *  # noqa


# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", ".ngrok-free.dev"]


# Development-specific CORS settings
# SECURITY: Never use CORS_ALLOW_ALL_ORIGINS even in development
CORS_ALLOW_ALL_ORIGINS = False

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",  # Django dev server
    "http://127.0.0.1:8000",
]

# Allow credentials in CORS requests (required for JWT)
CORS_ALLOW_CREDENTIALS = True


# Development database
# PostgreSQL для разработки (через Docker)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "foodmind"),  # noqa: F405
        "USER": os.getenv("POSTGRES_USER", "foodmind"),  # noqa: F405
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "foodmind"),  # noqa: F405
        "HOST": os.getenv("POSTGRES_HOST", "localhost"),  # noqa: F405
        "PORT": os.getenv("POSTGRES_PORT", "5432"),  # noqa: F405
    }
}


# Development-specific DRF settings
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [  # noqa: F405
    "rest_framework.renderers.JSONRenderer",
    "rest_framework.renderers.BrowsableAPIRenderer",  # Browsable API для разработки
]


# Logging configuration for development
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}


# Email backend for development (console)
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
