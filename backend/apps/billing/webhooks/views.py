from __future__ import annotations

import ipaddress
import logging
from typing import Any, Dict, Optional, Tuple

from django.conf import settings
from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.exceptions import ParseError
from rest_framework.permissions import AllowAny

from apps.billing.models import WebhookLog
from apps.billing.throttles import WebhookThrottle

from .handlers import handle_yookassa_event
from .utils import is_ip_allowed

logger = logging.getLogger(__name__)


# ============================================================
# Public entrypoint
# ============================================================

@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])              # публичный endpoint, защита через IP allowlist
@throttle_classes([WebhookThrottle])         # 100 req/hour per IP (пример)
def yookassa_webhook(request):
    """
    Webhook endpoint для YooKassa.

    Контроллер + firewall. Без бизнес-логики подписок.

    Поведение:
    - IP не разрешён -> 403
    - payload невалиден -> 400
    - валидно -> log + enqueue handler -> 200
    """

    client_ip = _get_client_ip_secure(request)

    # 1) Firewall: IP allowlist
    if not client_ip or not is_ip_allowed(client_ip):
        logger.warning(
            "[WEBHOOK_BLOCKED] ip=%s path=%s reason=not_in_allowlist",
            client_ip, request.path
        )
        return JsonResponse({"error": {"code": "FORBIDDEN"}}, status=403)

    # 2) Парсинг JSON (DRF-safe)
    try:
        payload = request.data
    except ParseError as e:
        logger.warning("[WEBHOOK_BAD_JSON] ip=%s err=%s", client_ip, str(e))
        return JsonResponse(
            {"error": {"code": "INVALID_JSON", "message": "Invalid JSON payload"}},
            status=400,
        )

    if not isinstance(payload, dict):
        logger.warning("[WEBHOOK_BAD_JSON] ip=%s payload_type=%s", client_ip, type(payload).__name__)
        return JsonResponse(
            {"error": {"code": "INVALID_JSON", "message": "Expected JSON object"}},
            status=400,
        )

    # 3) Мини-валидация структуры
    event_type, obj, obj_id, obj_status = _extract_event_fields(payload)
    if not event_type or not obj_id:
        logger.warning(
            "[WEBHOOK_INVALID_PAYLOAD] ip=%s event=%s obj_id=%s",
            client_ip, event_type, obj_id
        )
        return JsonResponse(
            {"error": {"code": "INVALID_PAYLOAD", "message": "Missing required fields"}},
            status=400,
        )

    # 4) Идемпотентность (правильная): ключ = event_type + object.id + object.status
    # Почему так: у одного payment_id может быть много событий.
    idempotency_key = f"{event_type}:{obj_id}:{obj_status or 'unknown'}"

    # 5) Логируем событие и решаем: новое/дубликат
    now = timezone.now()

    with transaction.atomic():
        log, created = WebhookLog.objects.select_for_update().get_or_create(
            event_id=idempotency_key,  # используем существующее поле как idempotency_key
            defaults={
                "event_type": event_type,
                "payment_id": _extract_payment_id(payload),
                "status": "RECEIVED",
                "raw_payload": payload,      # можно оставить, но следи за размером
                "client_ip": client_ip,
                "attempts": 1,
            },
        )

        if not created:
            # Это повторная доставка того же события (обычно ретрай)
            # НЕ перетираем SUCCESS/FAILED. Просто фиксируем, что видели ещё раз.
            log.attempts = (log.attempts or 0) + 1
            # если есть поле last_seen_at — обнови; если нет — можно обновить processed_at не трогая статус
            log.processed_at = log.processed_at or now
            log.save(update_fields=["attempts", "processed_at"])
            logger.info(
                "[WEBHOOK_DUPLICATE] key=%s status=%s attempts=%s",
                idempotency_key, log.status, log.attempts
            )
            return JsonResponse({"status": "ok"}, status=200)

        # новое событие
        log.status = "QUEUED"
        log.save(update_fields=["status"])

    # 6) Быстро отдаём 200 и обрабатываем в фоне (если есть celery task)
    # Если задачи нет — fallback на синхронную обработку (но это хуже).
    queued = _enqueue_processing(log_id=log.id, event_type=event_type, payload=payload)

    if not queued:
        # fallback: синхронно (лучше чем потерять событие)
        _process_webhook_sync(log_id=log.id, event_type=event_type, payload=payload)

    return JsonResponse({"status": "ok"}, status=200)


# ============================================================
# Processing (async preferred)
# ============================================================

def _enqueue_processing(*, log_id: int, event_type: str, payload: Dict[str, Any]) -> bool:
    """
    Пытаемся отдать обработку в фон.
    Вернёт True, если задача успешно поставлена.
    """
    try:
        # Celery task для асинхронной обработки
        from apps.billing.webhooks.tasks import process_yookassa_webhook  # type: ignore

        # Передаем только log_id - task сам достанет остальное из БД
        process_yookassa_webhook.delay(log_id)
        logger.info("[WEBHOOK_QUEUED] log_id=%s event=%s", log_id, event_type)
        return True
    except Exception as e:
        # Task может не существовать или Celery недоступен — это ок, будем fallback
        logger.warning(
            "[WEBHOOK_QUEUE_MISSING] log_id=%s event=%s fallback=sync err=%s",
            log_id, event_type, str(e)
        )
        return False


def _process_webhook_sync(*, log_id: int, event_type: str, payload: Dict[str, Any]) -> None:
    """
    Синхронный fallback. Используй только если фоновой обработки пока нет.
    """
    try:
        WebhookLog.objects.filter(id=log_id).update(status="PROCESSING")
        handle_yookassa_event(event_type=event_type, payload=payload)
        WebhookLog.objects.filter(id=log_id).update(status="SUCCESS", processed_at=timezone.now())
        logger.info("[WEBHOOK_PROCESSED_SYNC] log_id=%s ok=true", log_id)
    except Exception as e:
        WebhookLog.objects.filter(id=log_id).update(
            status="FAILED",
            error_message=str(e),
            processed_at=timezone.now(),
        )
        logger.error("[WEBHOOK_PROCESSED_SYNC] log_id=%s ok=false err=%s", log_id, str(e), exc_info=True)


# ============================================================
# Helpers (security + parsing)
# ============================================================

def _extract_event_fields(payload: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, Any], Optional[str], Optional[str]]:
    event_type = payload.get("event")
    obj = payload.get("object") or {}
    if not isinstance(obj, dict):
        obj = {}
    obj_id = obj.get("id")
    obj_status = obj.get("status")  # у payment есть status
    return event_type, obj, obj_id, obj_status


def _extract_payment_id(payload: Dict[str, Any]) -> Optional[str]:
    obj = payload.get("object") or {}
    if not isinstance(obj, dict):
        return None

    # YooKassa: object.object = "payment" / "refund"
    if obj.get("object") == "payment":
        return obj.get("id")
    if obj.get("object") == "refund":
        return obj.get("payment_id")
    return obj.get("id")


def _get_client_ip_secure(request: HttpRequest) -> Optional[str]:
    """
    Безопасное извлечение IP клиента.

    - По умолчанию НЕ доверяем XFF.
    - Если WEBHOOK_TRUST_XFF=True, то доверяем XFF только когда REMOTE_ADDR в trusted proxies.
    """
    remote_addr = request.META.get("REMOTE_ADDR", "") or ""
    trust_xff = bool(getattr(settings, "WEBHOOK_TRUST_XFF", False))

    # если доверие XFF выключено — просто REMOTE_ADDR
    if not trust_xff:
        # логируем только для дебага
        if request.META.get("HTTP_X_FORWARDED_FOR"):
            logger.debug(
                "[WEBHOOK_SECURITY] xff_present_ignored trust_xff=false remote_addr=%s",
                remote_addr
            )
        return remote_addr or None

    # доверие XFF включено — но только если прокси доверенный
    if not _is_trusted_proxy(remote_addr):
        logger.warning(
            "[WEBHOOK_SECURITY] xff_ignored_untrusted_proxy remote_addr=%s",
            remote_addr
        )
        return remote_addr or None

    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if not xff:
        return remote_addr or None

    real_ip = xff.split(",")[0].strip()
    return real_ip or None


def _is_trusted_proxy(ip: str) -> bool:
    """
    Trusted proxies берём из settings.WEBHOOK_TRUSTED_PROXIES

    Поддержка:
    - "127.0.0.1"
    - "172.23.0.0/16"
    """
    proxies = getattr(settings, "WEBHOOK_TRUSTED_PROXIES", None)
    if not proxies:
        # безопасный дефолт — только localhost
        proxies = ["127.0.0.1"]

    try:
        ip_obj = ipaddress.ip_address(ip)
    except ValueError:
        return False

    for item in proxies:
        try:
            item = str(item).strip()
            if not item:
                continue
            if "/" in item:
                net = ipaddress.ip_network(item, strict=False)
                if ip_obj in net:
                    return True
            else:
                if ip == item:
                    return True
        except ValueError:
            logger.warning("[WEBHOOK_SECURITY] invalid_trusted_proxy=%s", item)
            continue

    return False
