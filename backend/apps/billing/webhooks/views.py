"""
Webhook endpoint для YooKassa.

Задачи этого файла:
- принять webhook-запрос от YooKassa
- проверить, что запрос пришёл с разрешённого IP
- распарсить событие
- обеспечить ИДЕМПОТЕНТНОСТЬ (одно событие = одна обработка)
- передать событие в handlers
- всегда быстро отвечать 200 OK (если запрос валиден)

ВАЖНО:
- здесь НЕТ бизнес-логики
- здесь НЕТ работы с подписками напрямую
- этот файл — "контроллер + firewall"
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.billing.models import WebhookLog

from .handlers import handle_yookassa_event
from .utils import is_ip_allowed

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def yookassa_webhook(request: HttpRequest):
    """
    Единственная точка входа для webhook YooKassa.

    URL:
        POST /api/v1/billing/webhooks/yookassa

    Поведение:
    - если IP не разрешён → 403
    - если payload невалиден → 400
    - если событие уже обработано → 200 (идемпотентность)
    - если всё ок → передаём в handlers → 200
    """

    client_ip = _get_client_ip(request)

    # 1️⃣ Проверка IP (базовая защита)
    if not is_ip_allowed(client_ip):
        logger.warning(f"Blocked YooKassa webhook from IP {client_ip}")
        return JsonResponse(
            {"error": "forbidden"},
            status=403
        )

    # 2️⃣ Парсинг JSON
    try:
        payload: Dict[str, Any] = json.loads(request.body.decode("utf-8"))
    except Exception:
        logger.error("Invalid JSON payload from YooKassa")
        return JsonResponse(
            {"error": "invalid_json"},
            status=400
        )

    event_type = payload.get("event")
    event_object = payload.get("object", {})
    event_id = event_object.get("id")  # payment_id или refund_id

    if not event_type or not event_id:
        logger.error(f"Malformed webhook payload: {payload}")
        return JsonResponse(
            {"error": "invalid_payload"},
            status=400
        )

    # 3️⃣ Идемпотентность по event_id
    # Один webhook от YooKassa = один WebhookLog
    with transaction.atomic():
        webhook_log, created = WebhookLog.objects.select_for_update().get_or_create(
            event_id=event_id,
            defaults={
                "event_type": event_type,
                "payment_id": _extract_payment_id(payload),
                "status": "RECEIVED",
                "raw_payload": payload,
                "client_ip": client_ip,
            }
        )

        if not created:
            # webhook уже был получен ранее
            logger.info(
                f"Duplicate YooKassa webhook ignored: event_id={event_id}, status={webhook_log.status}"
            )
            webhook_log.status = "DUPLICATE"
            webhook_log.processed_at = timezone.now()
            webhook_log.save(update_fields=["status", "processed_at"])
            return JsonResponse({"status": "ok"})  # ВСЕГДА 200 для YooKassa

        # помечаем, что начали обработку
        webhook_log.status = "PROCESSING"
        webhook_log.attempts += 1
        webhook_log.save(update_fields=["status", "attempts"])

    # 4️⃣ Передаём событие в бизнес-обработчик
    try:
        handle_yookassa_event(event_type=event_type, payload=payload)

        # если всё прошло успешно
        webhook_log.status = "SUCCESS"
        webhook_log.processed_at = timezone.now()
        webhook_log.save(update_fields=["status", "processed_at"])

    except Exception as e:
        # ошибка обработки — webhook считается FAILED,
        # но YooKassa всё равно получит 200 (иначе будет ретраить)
        logger.error(
            f"Webhook processing error for event_id={event_id}: {str(e)}",
            exc_info=True
        )
        webhook_log.status = "FAILED"
        webhook_log.error_message = str(e)
        webhook_log.processed_at = timezone.now()
        webhook_log.save(update_fields=["status", "error_message", "processed_at"])

    # 5️⃣ Ответ YooKassa
    # ВАЖНО: всегда 200, если IP и JSON валидны
    return JsonResponse({"status": "ok"})


# ---------------------------------------------------------------------
# helpers (локальные, не бизнес-логика)
# ---------------------------------------------------------------------

def _get_client_ip(request: HttpRequest) -> str | None:
    """
    Аккуратно извлекаем IP клиента.

    Используем X-Forwarded-For, если есть (reverse proxy),
    иначе REMOTE_ADDR.
    """
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _extract_payment_id(payload: Dict[str, Any]) -> str | None:
    """
    Извлекает payment_id из payload, если он есть.
    Нужно для удобной фильтрации логов.
    """
    obj = payload.get("object", {})
    if obj.get("object") == "payment":
        return obj.get("id")
    if obj.get("object") == "refund":
        return obj.get("payment_id")
    return None
