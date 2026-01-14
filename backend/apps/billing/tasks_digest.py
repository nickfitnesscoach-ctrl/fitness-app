"""
Weekly billing digest task.

Purpose: Provides a weekly summary of billing webhook processing health.
Replaces manual log reading with a single informative report sent to admins.

Schedule: Monday 10:00 MSK (07:00 UTC) via Celery Beat
Delivery: Telegram message to TELEGRAM_ADMINS
"""

from __future__ import annotations

from collections import Counter
from datetime import timedelta
import logging

from celery import shared_task
from django.utils import timezone

from apps.billing.models import WebhookLog

logger = logging.getLogger(__name__)


def _send_telegram_alert(message: str) -> bool:
    """
    Send alert to Telegram admins.

    Uses HTTP API directly to avoid dependency on bot module.
    Reuses the same implementation as alert_failed_webhooks task.
    """
    from django.conf import settings
    import requests

    bot_token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)
    admin_ids = getattr(settings, "TELEGRAM_ADMINS", set())

    if not bot_token or not admin_ids:
        logger.warning("[WEEKLY_DIGEST] bot_token or admin_ids not configured")
        return False

    # TELEGRAM_ADMINS can be a string with IDs separated by commas or set/list
    if isinstance(admin_ids, str):
        admin_ids = [x.strip() for x in admin_ids.split(",") if x.strip()]

    success = False
    for admin_id in admin_ids:
        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            resp = requests.post(
                url,
                json={
                    "chat_id": admin_id,
                    "text": message,
                    "parse_mode": "HTML",
                },
                timeout=10,
            )
            if resp.status_code == 200:
                success = True
            else:
                logger.error("[WEEKLY_DIGEST] failed to send to %s: %s", admin_id, resp.text)
        except Exception as e:
            logger.error("[WEEKLY_DIGEST] error sending to %s: %s", admin_id, e)

    return success


def _group_errors_by_signature(failed_events) -> dict[str, int]:
    """
    Group errors by signature (exception class + first line of message).

    Returns:
        dict mapping error_signature -> count

    Example:
        {
            "OperationalError: FOR UPDATE cannot be applied...": 5,
            "Timeout: waiting for YooKassa API": 3
        }
    """
    error_counts = Counter()

    for event in failed_events:
        error_msg = event.error_message
        if error_msg is None or error_msg == "":
            signature = "(no error message)"
        else:
            # Take first line only (up to first newline or 100 chars)
            first_line = error_msg.split("\n")[0][:100]
            signature = first_line.strip()
            if not signature:
                signature = "(no error message)"

        error_counts[signature] += 1

    return dict(error_counts)


def _format_weekly_digest(stats: dict) -> str:
    """
    Format weekly digest message in HTML for Telegram.

    Args:
        stats: dict with keys:
            - total_events: int
            - success_count: int
            - failed_count: int
            - failed_by_type: dict[str, int] (event_type -> count)
            - top_errors: list[tuple[str, int]] (error_signature, count)
            - period_start: str (formatted date)
            - period_end: str (formatted date)

    Returns:
        Formatted HTML message for Telegram
    """
    total = stats["total_events"]
    success = stats["success_count"]
    failed = stats["failed_count"]
    period_start = stats["period_start"]
    period_end = stats["period_end"]

    # Header
    message = "📊 <b>WEEKLY BILLING DIGEST</b>\n" f"Период: {period_start} → {period_end}\n\n"

    # If no events at all
    if total == 0:
        message += "⚠️ Нет webhook событий за период\n"
        return message

    # If no failures (success path)
    if failed == 0:
        message += "✅ <b>Все billing webhooks обработаны успешно</b>\n"
        message += f"Всего событий: {total}\n"
        message += "Ошибок нет\n"
        return message

    # General summary (with failures)
    message += f"Всего webhook событий: {total}\n"
    message += f"Успешно обработано: {success}\n"
    message += f"Failed webhooks: {failed} ⚠️\n\n"

    # Breakdown by event_type
    failed_by_type = stats.get("failed_by_type", {})
    if failed_by_type:
        message += "<b>Ошибки по типам:</b>\n"
        for event_type, count in sorted(failed_by_type.items(), key=lambda x: x[1], reverse=True):
            message += f"• <code>{event_type}</code> — {count}\n"
        message += "\n"

    # Top errors
    top_errors = stats.get("top_errors", [])
    if top_errors:
        message += "<b>Топ ошибок:</b>\n"
        for error_sig, count in top_errors[:3]:  # Top 3
            # Escape HTML special chars
            error_escaped = (
                error_sig.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            )
            message += f"• {error_escaped} — {count}\n"

    return message


@shared_task(queue="billing", bind=True, max_retries=3)
def send_weekly_billing_digest(self):
    """
    Send weekly digest about billing webhook processing health.

    Runs every Monday at 10:00 MSK (07:00 UTC) via Celery Beat.

    Data source: WebhookLog.objects (last 7 days)
    Delivery: Telegram message to TELEGRAM_ADMINS

    Format:
        - General summary (total events, success, failed)
        - Breakdown by event_type (if failures exist)
        - Top 3 errors by signature (if failures exist)

    Safety:
        - Does NOT create failed webhook if digest sending fails
        - Logs errors instead of raising exceptions
        - Limited retries (max 3) to avoid infinite loops
    """
    try:
        # Calculate period (last 7 days)
        end_date = timezone.now()
        start_date = end_date - timedelta(days=7)

        # Format dates for display
        period_start_str = start_date.strftime("%Y-%m-%d")
        period_end_str = end_date.strftime("%Y-%m-%d")

        logger.info(
            "[WEEKLY_DIGEST] Generating digest for period %s → %s",
            period_start_str,
            period_end_str,
        )

        # Query webhook events in period
        events_in_period = WebhookLog.objects.filter(
            created_at__gte=start_date, created_at__lte=end_date
        )

        total_events = events_in_period.count()
        success_events = events_in_period.filter(status="SUCCESS")
        success_count = success_events.count()
        failed_events = events_in_period.filter(status="FAILED")
        failed_count = failed_events.count()

        # Build stats dictionary
        stats = {
            "total_events": total_events,
            "success_count": success_count,
            "failed_count": failed_count,
            "period_start": period_start_str,
            "period_end": period_end_str,
        }

        # If there are failures, add breakdown
        if failed_count > 0:
            # Group by event_type (Django ORM grouping)
            failed_by_type_counts = {}
            for event in failed_events:
                event_type = event.event_type
                failed_by_type_counts[event_type] = failed_by_type_counts.get(event_type, 0) + 1
            stats["failed_by_type"] = failed_by_type_counts

            # Group errors by signature
            error_signatures = _group_errors_by_signature(failed_events)
            # Top 3 errors
            top_errors = sorted(error_signatures.items(), key=lambda x: x[1], reverse=True)[:3]
            stats["top_errors"] = top_errors

        # Format message
        message = _format_weekly_digest(stats)

        # Send to admins
        send_success = _send_telegram_alert(message)

        if send_success:
            logger.info(
                "[WEEKLY_DIGEST] Successfully sent digest for period %s → %s (total=%d, failed=%d)",
                period_start_str,
                period_end_str,
                total_events,
                failed_count,
            )
        else:
            logger.error(
                "[WEEKLY_DIGEST] Failed to send digest to admins (period %s → %s)",
                period_start_str,
                period_end_str,
            )

        return {
            "success": send_success,
            "period": f"{period_start_str} → {period_end_str}",
            "total_events": total_events,
            "failed_count": failed_count,
        }

    except Exception as exc:
        logger.error("[WEEKLY_DIGEST] Error generating digest: %s", exc, exc_info=True)
        # Do NOT raise exception to avoid creating failed webhook
        # Just log and return failure
        return {"success": False, "error": str(exc)}
