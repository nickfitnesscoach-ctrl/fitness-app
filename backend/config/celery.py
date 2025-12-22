"""
Celery configuration for FoodMind AI project.

Usage:
    # Start worker
    celery -A config worker -l info

    # Start beat (for periodic tasks)
    celery -A config beat -l info
"""

import os

from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

app = Celery("foodmind")

# Load config from Django settings with CELERY_ prefix
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()


# =============================================================================
# Celery Beat Schedule (Periodic Tasks)
# =============================================================================
app.conf.beat_schedule = {
    # P1-WH-01: Recovery для застрявших webhooks
    "billing-retry-stuck-webhooks": {
        "task": "apps.billing.webhooks.tasks.retry_stuck_webhooks",
        "schedule": crontab(minute="*/5"),  # каждые 5 минут
    },
    # P2-WH-02: Alerting для FAILED webhooks
    "billing-alert-failed-webhooks": {
        "task": "apps.billing.webhooks.tasks.alert_failed_webhooks",
        "schedule": crontab(minute="*/15"),  # каждые 15 минут
    },
    # P2-PL-01: Cleanup PENDING платежей > 24h
    "billing-cleanup-pending-payments": {
        "task": "apps.billing.webhooks.tasks.cleanup_pending_payments",
        "schedule": crontab(minute=0, hour="*/1"),  # каждый час в :00
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery setup."""
    print(f"Request: {self.request!r}")
