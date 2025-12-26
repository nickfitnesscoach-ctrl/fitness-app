from __future__ import annotations

import ipaddress
import logging
import uuid
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

    Observability:
    - trace_id генерируется для каждого входящего webhook
    - Все логи содержат trace_id для корреляции
    """
    # Generate trace_id for this request
    trace_id = str(uuid.uuid4())[:8]  # Short trace ID for readability

    client_ip, remote_addr = _get_client_ip_secure(request)

    # 1) Firewall: IP allowlist
    if not client_ip or not is_ip_allowed(client_ip):
        logger.warning(
            "[WEBHOOK_BLOCKED] trace_id=%s ip=%s remote_addr=%s path=%s reason=not_in_allowlist",
            trace_id, client_ip, remote_addr, request.path
        )
        return JsonResponse({"error": {"code": "FORBIDDEN"}}, status=403)

    logger.info(
        "[WEBHOOK_RECEIVED] trace_id=%s ip=%s remote_addr=%s",
        trace_id, client_ip, remote_addr
    )

    # 2) Парсинг JSON (DRF-safe)
    try:
        payload = request.data
    except ParseError as e:
        logger.warning("[WEBHOOK_BAD_JSON] trace_id=%s ip=%s err=%s", trace_id, client_ip, str(e))
        return JsonResponse(
            {"error": {"code": "INVALID_JSON", "message": "Invalid JSON payload"}},
            status=400,
        )

    if not isinstance(payload, dict):
        logger.warning("[WEBHOOK_BAD_JSON] trace_id=%s ip=%s payload_type=%s", trace_id, client_ip, type(payload).__name__)
        return JsonResponse(
            {"error": {"code": "INVALID_JSON", "message": "Expected JSON object"}},
            status=400,
        )

    # 3) Мини-валидация структуры + извлечение provider_event_id
    event_type, obj, obj_id, obj_status = _extract_event_fields(payload)
    provider_event_id = _extract_provider_event_id(payload)

    if not event_type or not obj_id:
        logger.warning(
            "[WEBHOOK_INVALID_PAYLOAD] trace_id=%s ip=%s event=%s obj_id=%s",
            trace_id, client_ip, event_type, obj_id
        )
        return JsonResponse(
            {"error": {"code": "INVALID_PAYLOAD", "message": "Missing required fields"}},
            status=400,
        )

    # 4) Идемпотентность:
    # - Primary: provider_event_id (если есть от YooKassa)
    # - Fallback: event_type:obj_id:obj_status
    if provider_event_id:
        idempotency_key = provider_event_id
    else:
        idempotency_key = f"{event_type}:{obj_id}:{obj_status or 'unknown'}"

    # 5) Логируем событие и решаем: новое/дубликат
    now = timezone.now()

    with transaction.atomic():
        log, created = WebhookLog.objects.select_for_update().get_or_create(
            event_id=idempotency_key,
            defaults={
                "event_type": event_type,
                "payment_id": _extract_payment_id(payload),
                "provider_event_id": provider_event_id,
                "trace_id": trace_id,
                "status": "RECEIVED",
                "raw_payload": _sanitize_payload(payload),
                "client_ip": client_ip,
                "attempts": 1,
            },
        )

        if not created:
            # Это повторная доставка того же события (обычно ретрай)
            # НЕ перетираем SUCCESS/FAILED. Просто фиксируем, что видели ещё раз.
            log.attempts = (log.attempts or 0) + 1
            log.processed_at = log.processed_at or now
            log.save(update_fields=["attempts", "processed_at"])
            logger.info(
                "[WEBHOOK_DUPLICATE] trace_id=%s provider_event_id=%s key=%s status=%s attempts=%s",
                trace_id, provider_event_id, idempotency_key, log.status, log.attempts
            )
            return JsonResponse({"status": "ok"}, status=200)

        # новое событие
        log.status = "QUEUED"
        log.save(update_fields=["status"])

    # 6) Быстро отдаём 200 и обрабатываем в фоне (если есть celery task)
    queued = _enqueue_processing(
        log_id=log.id,
        event_type=event_type,
        payload=payload,
        trace_id=trace_id,
    )

    if not queued:
        # fallback: синхронно (лучше чем потерять событие)
        _process_webhook_sync(log_id=log.id, event_type=event_type, payload=payload, trace_id=trace_id)

    return JsonResponse({"status": "ok"}, status=200)


# ============================================================
# Processing (async preferred)
# ============================================================

def _enqueue_processing(*, log_id: int, event_type: str, payload: Dict[str, Any], trace_id: str) -> bool:
    """
    Пытаемся отдать обработку в фон.
    Вернёт True, если задача успешно поставлена.
    """
    try:
        from apps.billing.webhooks.tasks import process_yookassa_webhook

        # Передаем log_id и trace_id для корреляции логов
        task = process_yookassa_webhook.delay(log_id, trace_id=trace_id)
        logger.info(
            "[WEBHOOK_QUEUED] trace_id=%s log_id=%s task_id=%s event=%s",
            trace_id, log_id, task.id, event_type
        )
        return True
    except Exception as e:
        logger.warning(
            "[WEBHOOK_QUEUE_MISSING] trace_id=%s log_id=%s event=%s fallback=sync err=%s",
            trace_id, log_id, event_type, str(e)
        )
        return False


def _process_webhook_sync(*, log_id: int, event_type: str, payload: Dict[str, Any], trace_id: str) -> None:
    """
    Синхронный fallback. Используй только если фоновой обработки пока нет.
    """
    try:
        WebhookLog.objects.filter(id=log_id).update(status="PROCESSING")
        logger.info("[WEBHOOK_TASK_START] trace_id=%s log_id=%s sync=true", trace_id, log_id)
        handle_yookassa_event(event_type=event_type, payload=payload, trace_id=trace_id)
        WebhookLog.objects.filter(id=log_id).update(status="SUCCESS", processed_at=timezone.now())
        logger.info("[WEBHOOK_TASK_DONE] trace_id=%s log_id=%s ok=true sync=true", trace_id, log_id)
    except Exception as e:
        WebhookLog.objects.filter(id=log_id).update(
            status="FAILED",
            error_message=str(e),
            processed_at=timezone.now(),
        )
        logger.error(
            "[WEBHOOK_TASK_DONE] trace_id=%s log_id=%s ok=false sync=true err=%s",
            trace_id, log_id, str(e), exc_info=True
        )


# ============================================================
# Helpers (security + parsing)
# ============================================================

def _extract_event_fields(payload: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, Any], Optional[str], Optional[str]]:
    event_type = payload.get("event")
    obj = payload.get("object") or {}
    if not isinstance(obj, dict):
        obj = {}
    obj_id = obj.get("id")
    obj_status = obj.get("status")
    return event_type, obj, obj_id, obj_status


def _extract_provider_event_id(payload: Dict[str, Any]) -> Optional[str]:
    """
    Извлекает event_id от провайдера (YooKassa).

    YooKassa может присылать:
    - payload.id — ID уведомления (некоторые версии API)
    - payload.uuid — альтернативный ID

    Если нет — возвращаем None (будет использован fallback).
    """
    # YooKassa notification ID (если присутствует)
    if payload.get("uuid"):
        return str(payload["uuid"])
    if payload.get("id") and payload.get("type") == "notification":
        return str(payload["id"])
    return None


def _extract_payment_id(payload: Dict[str, Any]) -> Optional[str]:
    obj = payload.get("object") or {}
    if not isinstance(obj, dict):
        return None

    if obj.get("object") == "payment":
        return obj.get("id")
    if obj.get("object") == "refund":
        return obj.get("payment_id")
    return obj.get("id")


def _sanitize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Редактирует чувствительные данные перед сохранением в БД.

    Удаляем/маскируем:
    - payment_method.card (кроме last4)
    """
    safe = {**payload}
    obj = safe.get("object")
    if isinstance(obj, dict):
        safe["object"] = {**obj}
        pm = safe["object"].get("payment_method")
        if isinstance(pm, dict):
            # Оставляем только id и type, маскируем card
            safe["object"]["payment_method"] = {
                "id": pm.get("id"),
                "type": pm.get("type"),
                "saved": pm.get("saved"),
                "card": {"last4": pm.get("card", {}).get("last4"), "redacted": True} if pm.get("card") else None,
            }
    return safe


def _get_client_ip_secure(request: HttpRequest) -> Tuple[Optional[str], str]:
    """
    Безопасное извлечение IP клиента.

    Returns:
        Tuple of (effective_client_ip, remote_addr)

    Security:
    - По умолчанию НЕ доверяем XFF.
    - Если WEBHOOK_TRUST_XFF=True, то доверяем XFF только когда REMOTE_ADDR в trusted proxies.
    - Логируем попытки спуфинга XFF.
    """
    remote_addr = request.META.get("REMOTE_ADDR", "") or ""
    trust_xff = bool(getattr(settings, "WEBHOOK_TRUST_XFF", False))
    xff = request.META.get("HTTP_X_FORWARDED_FOR")

    # если доверие XFF выключено — просто REMOTE_ADDR
    if not trust_xff:
        if xff:
            logger.debug(
                "[WEBHOOK_SECURITY] xff_present_ignored trust_xff=false remote_addr=%s xff=%s",
                remote_addr, xff
            )
        return remote_addr or None, remote_addr

    # доверие XFF включено — но только если прокси доверенный
    if not _is_trusted_proxy(remote_addr):
        logger.warning(
            "[WEBHOOK_SECURITY] xff_ignored_untrusted_proxy remote_addr=%s xff=%s",
            remote_addr, xff
        )
        return remote_addr or None, remote_addr

    if not xff:
        return remote_addr or None, remote_addr

    real_ip = xff.split(",")[0].strip()
    logger.debug(
        "[WEBHOOK_SECURITY] xff_trusted remote_addr=%s xff=%s real_ip=%s",
        remote_addr, xff, real_ip
    )
    return real_ip or None, remote_addr


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
