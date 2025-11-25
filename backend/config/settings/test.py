"""
Test settings for FoodMind AI project.
Uses SQLite for faster test execution and to avoid PostgreSQL connection issues.
"""

from .base import *

# Use SQLite for tests (faster and no connection issues)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',  # In-memory database for tests
    }
}

# Disable migrations for faster tests
class DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None

# Comment out the line below if you want to run migrations during tests
# MIGRATION_MODULES = DisableMigrations()

# Use MD5 password hasher for faster tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Disable logging during tests
LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
}

# Use console email backend for tests
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Speed up tests
DEBUG = False
TEMPLATE_DEBUG = False
