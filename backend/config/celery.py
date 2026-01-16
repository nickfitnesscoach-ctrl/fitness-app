"""
Celery configuration for EatFit24 project.

Usage:
    # Start worker (requires DJANGO_SETTINGS_MODULE set via env)
    celery -A config worker -l info -Q ai,billing,default

    # Start beat (for periodic tasks)
    celery -A config beat -l info
"""

import logging
import os

from celery import Celery
from celery.schedules import crontab

# CRITICAL: DJANGO_SETTINGS_MODULE must be set explicitly via environment
# DO NOT use setdefault here - it can cause local settings to load in production
# The entrypoint.sh and compose files are responsible for setting this correctly
if not os.environ.get("DJANGO_SETTINGS_MODULE"):
    raise RuntimeError(
        "[CELERY] DJANGO_SETTINGS_MODULE is not set. Set it via .env file or compose environment."
    )

app = Celery("eatfit24")

# Load config from Django settings with CELERY_ prefix
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

# Setup logger for Celery config
logger = logging.getLogger(__name__)


# =============================================================================
# Lazy Task Registration (for non-standard task modules)
# =============================================================================
# Explicitly register tasks from non-standard modules (not tasks.py)
# Required because autodiscover_tasks() only finds tasks.py by default
# Uses app.on_after_finalize to avoid AppRegistryNotReady errors
@app.on_after_finalize.connect
def register_additional_tasks(sender, **kwargs):
    """Import tasks from non-standard modules after Celery is configured."""
    from apps.billing import tasks_digest  # noqa: F401


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
        "schedule": crontab(
            hour=10, minute=0, day_of_week=1
        ),  # Mon 10:00 MSK (CELERY_TIMEZONE=Europe/Moscow)
    },
    # P4-DIG-02: Weekly digest health check (silent degradation guard)
    "billing-digest-health-check": {
        "task": "apps.billing.tasks_digest.check_weekly_digest_health",
        "schedule": crontab(hour=12, minute=0),  # Daily 12:00 MSK (CELERY_TIMEZONE=Europe/Moscow)
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
