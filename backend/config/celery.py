"""
Celery configuration for FoodMind AI project.

Usage:
    # Start worker
    celery -A config worker -l info

    # Start beat (for periodic tasks)
    celery -A config beat -l info
"""

import logging
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

# Setup logger for Celery config
logger = logging.getLogger(__name__)


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


# =============================================================================
# Startup Logging & Guardrails
# =============================================================================
@app.on_after_configure.connect
def log_celery_config(sender, **kwargs):
    """
    Log Celery configuration at startup for debugging and monitoring.

    This helps catch configuration issues early:
    - Timezone mismatches
    - Empty beat_schedule in production
    - Missing tasks
    """
    config = sender.conf

    # Log timezone configuration
    logger.info("=" * 60)
    logger.info("[CELERY CONFIG] Startup configuration:")
    logger.info(f"  timezone: {config.timezone}")
    logger.info(f"  enable_utc: {config.enable_utc}")

    # Log beat schedule
    schedule = config.beat_schedule or {}
    task_count = len(schedule)
    logger.info(f"  beat_schedule: {task_count} task(s) configured")

    # Warn if empty in production
    if task_count == 0:
        logger.warning(
            "[CELERY CONFIG] ⚠️  WARNING: beat_schedule is EMPTY! "
            "No periodic tasks will run."
        )
    else:
        logger.info("  Periodic tasks:")
        for task_name, task_config in schedule.items():
            schedule_str = task_config.get("schedule", "N/A")
            task_path = task_config.get("task", "N/A")
            logger.info(f"    ✓ {task_name}")
            logger.info(f"      schedule: {schedule_str}")
            logger.info(f"      task: {task_path}")

    logger.info("=" * 60)


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery setup."""
    print(f"Request: {self.request!r}")
