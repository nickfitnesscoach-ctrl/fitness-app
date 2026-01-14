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
# Queue Configuration (A5: Source of Truth)
# =============================================================================
# CRITICAL: Default queue must be explicitly set to avoid confusion.
# Tasks are routed to specific queues for isolation and priority.
#
# Queues:
# - billing: Payment webhooks, recurring payments (high priority)
# - ai: AI recognition tasks (can be slow, isolated)
# - default: Everything else
# =============================================================================

app.conf.task_default_queue = "default"

# Task routing: route specific tasks to dedicated queues
app.conf.task_routes = {
    # Billing tasks -> billing queue
    "apps.billing.webhooks.tasks.*": {"queue": "billing"},
    "apps.billing.tasks_recurring.*": {"queue": "billing"},
    "apps.billing.tasks_digest.*": {"queue": "billing"},
    # AI tasks -> ai queue
    "apps.ai.tasks.*": {"queue": "ai"},
}


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
    # Recurring: Auto-renew subscriptions
    "billing-process-due-renewals": {
        "task": "apps.billing.tasks_recurring.process_due_renewals",
        "schedule": crontab(minute=0, hour="*/1"),  # каждый час в :00
    },
    # P2-DIG-01: Weekly billing digest
    "billing-weekly-digest": {
        "task": "apps.billing.tasks_digest.send_weekly_billing_digest",
        "schedule": crontab(hour=7, minute=0, day_of_week=1),  # Пн 10:00 MSK = 07:00 UTC
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
    - Queue configuration
    """
    config = sender.conf

    # Log timezone configuration
    logger.info("=" * 60)
    logger.info("[CELERY CONFIG] Startup configuration:")
    logger.info("  timezone: %s", config.timezone)
    logger.info("  enable_utc: %s", config.enable_utc)

    # Log queue configuration
    logger.info("  task_default_queue: %s", config.task_default_queue)
    task_routes = config.task_routes or {}
    logger.info("  task_routes: %d route(s) configured", len(task_routes))
    for pattern, route in task_routes.items():
        queue = route.get("queue", "default") if isinstance(route, dict) else route
        logger.info("    %s -> %s", pattern, queue)

    # Log beat schedule
    schedule = config.beat_schedule or {}
    task_count = len(schedule)
    logger.info("  beat_schedule: %d task(s) configured", task_count)

    # Warn if empty in production
    if task_count == 0:
        logger.warning(
            "[CELERY CONFIG] ⚠️  WARNING: beat_schedule is EMPTY! No periodic tasks will run."
        )
    else:
        logger.info("  Periodic tasks:")
        for task_name, task_config in schedule.items():
            schedule_str = task_config.get("schedule", "N/A")
            task_path = task_config.get("task", "N/A")
            logger.info("    ✓ %s", task_name)
            logger.info("      schedule: %s", schedule_str)
            logger.info("      task: %s", task_path)

    logger.info("=" * 60)


# Log active queues when worker is starting
@app.on_after_finalize.connect
def log_worker_queues(sender, **kwargs):
    """
    Log the queues this worker is consuming.

    CRITICAL: This helps detect queue configuration regressions.
    If 'billing' queue is missing, webhooks won't be processed!
    """
    # Note: This only logs configuration, actual active queues are shown by -Q flag
    # The worker command should include: -Q ai,billing,default
    logger.info("[CELERY QUEUES] Worker queue configuration:")
    logger.info("  task_default_queue: %s", sender.conf.task_default_queue)
    logger.info("  ⚠️  REMINDER: Worker MUST be started with -Q ai,billing,default")


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery setup."""
    print(f"Request: {self.request!r}")
