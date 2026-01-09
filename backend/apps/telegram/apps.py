"""
Django AppConfig для приложения Telegram.
"""

from django.apps import AppConfig


class TelegramConfig(AppConfig):
    """Конфигурация приложения Telegram."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.telegram"
    verbose_name = "Telegram Integration"
