#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    # CRITICAL: Explicitly set SECRET_KEY in os.environ BEFORE Django imports
    # This fixes the circular import issue with rest_framework_simplejwt
    if "SECRET_KEY" not in os.environ and "DJANGO_SECRET_KEY" in os.environ:
        os.environ["SECRET_KEY"] = os.environ["DJANGO_SECRET_KEY"]

    # Use DJANGO_SETTINGS_MODULE from environment if set, otherwise default to local
    # In Docker containers, DJANGO_SETTINGS_MODULE is always set explicitly
    # For local development without env var, defaults to config.settings.local
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
