"""
Celery tasks for async webhook processing.

Production-grade асинхронная обработка webhook'ов от YooKassa.
"""

from celery import shared_task
from django.utils import timezone

from apps.billing.models import WebhookLog
from apps.billing.webhooks.handlers import handle_yookassa_event

import logging

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=5,
    default_retry_delay=30,
    ack_late=True,  # P1-CEL-02: Acknowledge after processing to prevent loss on worker crash
    queue="billing",  # P1-CEL-01: Dedicated queue to prevent AI tasks from blocking billing
)
def process_yookassa_webhook(self, log_id: int, trace_id: str = None):
    """
    Асинхронная обработка YooKassa webhook события.

    Args:
        log_id: ID записи WebhookLog для обработки
        trace_id: ID трейса для корреляции логов

    Retry strategy:
        - max_retries=5: максимум 5 попыток
        - default_retry_delay=30: задержка 30 секунд между попытками
        - Экспоненциальный backoff (30s, 60s, 120s, 240s, 480s)
        - ack_late=True: задача подтверждается ПОСЛЕ успешного выполнения

    Queue:
        - billing: отдельная очередь для платёжных задач

    Поведение:
        1. Загружает WebhookLog по ID
        2. Извлекает payload и event_type
        3. Обновляет статус на PROCESSING
        4. Вызывает handle_yookassa_event() для бизнес-логики
        5. При успехе: статус SUCCESS, processed_at = now
        6. При ошибке: статус FAILED, error_message, processed_at = now, retry
    """
    try:
        log = WebhookLog.objects.get(id=log_id)
    except WebhookLog.DoesNotExist:
        logger.error("[WEBHOOK_TASK_ERROR] trace_id=%s log_id=%s error=not_found", trace_id, log_id)
        # Не ретраим если запись удалена
        return

    # Fallback to trace_id from log if not provided
    if not trace_id:
        trace_id = getattr(log, "trace_id", None) or "unknown"

    payload = log.raw_payload
    event_type = log.event_type

    try:
        # Обновляем статус на PROCESSING
        WebhookLog.objects.filter(id=log_id).update(status="PROCESSING")
        logger.info(
            "[WEBHOOK_TASK_START] trace_id=%s log_id=%s task_id=%s event=%s",
            trace_id,
            log_id,
            self.request.id,
            event_type,
        )

        # Основная бизнес-логика
        handle_yookassa_event(event_type=event_type, payload=payload, trace_id=trace_id)

        # Успех
        WebhookLog.objects.filter(id=log_id).update(status="SUCCESS", processed_at=timezone.now())
        logger.info(
            "[WEBHOOK_TASK_DONE] trace_id=%s log_id=%s task_id=%s event=%s ok=true",
            trace_id,
            log_id,
            self.request.id,
            event_type,
        )

    except Exception as e:
        # Логируем ошибку
        error_msg = str(e)
        logger.error(
            "[WEBHOOK_TASK_DONE] trace_id=%s log_id=%s task_id=%s event=%s ok=false error=%s retry=%s/%s",
            trace_id,
            log_id,
            self.request.id,
            event_type,
            error_msg,
            self.request.retries,
            self.max_retries,
            exc_info=True,
        )

        # Обновляем статус на FAILED
        WebhookLog.objects.filter(id=log_id).update(
            status="FAILED",
            error_message=error_msg[:500],  # ограничиваем длину
            processed_at=timezone.now(),
        )

        # Ретраим задачу с экспоненциальным backoff
        if self.request.retries < self.max_retries:
            # Экспоненциальный backoff: 30, 60, 120, 240, 480 секунд
            delay = self.default_retry_delay * (2**self.request.retries)
            logger.info(
                "[WEBHOOK_TASK_RETRY] trace_id=%s log_id=%s retry=%s delay=%ss",
                trace_id,
                log_id,
                self.request.retries + 1,
                delay,
            )
            raise self.retry(exc=e, countdown=delay)
        else:
            logger.error(
                "[WEBHOOK_TASK_EXHAUSTED] trace_id=%s log_id=%s max_retries_reached",
                trace_id,
                log_id,
            )


@shared_task(queue="billing")
def retry_stuck_webhooks():
    """
    P1-WH-01: Recovery для застрявших webhooks.

    Находит WebhookLog записи в статусе PROCESSING более 10 минут
    и перезапускает их обработку.

    Рекомендуется запускать через Celery Beat каждые 5 минут:
        'retry-stuck-webhooks': {
            'task': 'apps.billing.webhooks.tasks.retry_stuck_webhooks',
            'schedule': crontab(minute='*/5'),
        }
    """
    from datetime import timedelta

    stuck_threshold = timezone.now() - timedelta(minutes=10)

    stuck = WebhookLog.objects.filter(status="PROCESSING", created_at__lt=stuck_threshold)

    count = stuck.count()
    if count == 0:
        logger.info("[WEBHOOK_RECOVERY] no stuck webhooks found")
        return

    logger.warning("[WEBHOOK_RECOVERY] found %s stuck webhooks, retrying...", count)

    for log in stuck:
        log.status = "QUEUED"
        log.error_message = f"Auto-retry: was stuck in PROCESSING since {log.created_at}"
        log.save(update_fields=["status", "error_message"])
        process_yookassa_webhook.delay(str(log.id))
        logger.info("[WEBHOOK_RECOVERY] requeued log_id=%s", log.id)

    logger.info("[WEBHOOK_RECOVERY] requeued %s stuck webhooks", count)


def _send_telegram_alert(message: str) -> bool:
    """
    Отправка алерта в Telegram админам.

    Используем HTTP API напрямую, чтобы не зависеть от bot модуля.
    """
    import requests
    from django.conf import settings

    bot_token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)
    admin_ids = getattr(settings, "TELEGRAM_ADMINS", set())

    if not bot_token or not admin_ids:
        logger.warning("[TELEGRAM_ALERT] bot_token or admin_ids not configured")
        return False

    # TELEGRAM_ADMINS может быть строкой с ID через запятую или set/list
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
                logger.error("[TELEGRAM_ALERT] failed to send to %s: %s", admin_id, resp.text)
        except Exception as e:
            logger.error("[TELEGRAM_ALERT] error sending to %s: %s", admin_id, e)

    return success


@shared_task(queue="billing")
def alert_failed_webhooks():
    """
    P2-WH-02: Alerting для FAILED webhooks.

    Находит FAILED webhooks за последний час и отправляет alert админам.
    Рекомендуется запускать через Celery Beat каждые 15 минут.
    """
    from datetime import timedelta

    since = timezone.now() - timedelta(hours=1)

    failed = WebhookLog.objects.filter(status="FAILED", processed_at__gte=since)

    count = failed.count()
    if count == 0:
        logger.info("[WEBHOOK_ALERT] no failed webhooks in last hour")
        return

    # Собираем детали для алерта
    details = []
    for log in failed[:5]:  # Максимум 5 примеров
        details.append(
            f"• {log.event_type}: {log.error_message[:100] if log.error_message else 'no message'}"
        )

    message = (
        f"🚨 <b>BILLING ALERT</b>\n\n"
        f"⚠️ {count} failed webhooks за последний час!\n\n"
        f"Примеры:\n" + "\n".join(details) + "\n\n"
        f"Проверьте логи: <code>docker logs eatfit24-celery-worker-1</code>"
    )

    _send_telegram_alert(message)
    logger.warning("[WEBHOOK_ALERT] sent alert for %s failed webhooks", count)


@shared_task(queue="billing")
def cleanup_pending_payments():
    """
    P2-PL-01: Cleanup для PENDING платежей старше 24 часов.

    PENDING платежи, которые не получили webhook более 24 часов,
    считаются "мёртвыми" и переводятся в CANCELED.

    Рекомендуется запускать через Celery Beat раз в час.
    """
    from datetime import timedelta
    from apps.billing.models import Payment

    threshold = timezone.now() - timedelta(hours=24)

    old_pending = Payment.objects.filter(status="PENDING", created_at__lt=threshold)

    count = old_pending.count()
    if count == 0:
        logger.info("[PAYMENT_CLEANUP] no stuck pending payments found")
        return

    # Обновляем статус
    updated = old_pending.update(
        status="CANCELED", error_message="Auto-canceled: no webhook received within 24 hours"
    )

    logger.warning("[PAYMENT_CLEANUP] canceled %s stuck pending payments", updated)

    # Отправляем алерт если много
    if updated >= 3:
        message = (
            f"⚠️ <b>BILLING CLEANUP</b>\n\n"
            f"Отменено {updated} PENDING платежей (старше 24ч)\n\n"
            f"Возможно, webhooks не доходят!"
        )
        _send_telegram_alert(message)
