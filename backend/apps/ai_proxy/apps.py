"""
Django app configuration for AI Proxy integration.
"""

from django.apps import AppConfig


class AiProxyConfig(AppConfig):
    """Configuration for AI Proxy app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ai_proxy"
    verbose_name = "AI Proxy Integration"
