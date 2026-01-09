"""
Admin/Trainer panel views для Telegram интеграции.

Зачем этот файл:
- Это API для "панели тренера" (админский доступ через Telegram WebApp).
- Здесь тренер смотрит:
  1) заявки (applications) — кто прошёл опрос/тест
  2) клиентов — те же заявки, но помеченные is_client=True
  3) подписчиков и выручку — метрики по оплатам

Главное правило безопасности:
- Эти ручки должны быть доступны ТОЛЬКО Telegram-админам.
  Поэтому везде стоит TelegramAdminPermission.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.telegram.models import TelegramUser
from apps.telegram.telegram_auth import TelegramAdminPermission
from apps.telegram.trainer_panel.billing_adapter import (
    get_revenue_metrics,
    get_subscribers_metrics,
    get_subscriptions_for_users,
)

logger = logging.getLogger(__name__)

# Безопасные лимиты по умолчанию, чтобы случайно не отдать 50к записей за раз
DEFAULT_LIMIT = 200
MAX_LIMIT = 1000


# ============================================================================
# Вспомогательные функции (чтобы не копировать одно и то же 3 раза)
# ============================================================================


def _safe_int(value: Any, field_name: str) -> int:
    """Пытаемся привести к int и проверяем, что число положительное."""
    try:
        ivalue = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be an integer")
    if ivalue <= 0:
        raise ValueError(f"{field_name} must be positive")
    return ivalue


def _get_pagination_params(request) -> tuple[int, int]:
    """
    Простая пагинация через limit/offset.
    Если не задано — отдаём DEFAULT_LIMIT.
    """
    raw_limit = request.query_params.get("limit", DEFAULT_LIMIT)
    raw_offset = request.query_params.get("offset", 0)

    try:
        limit = _safe_int(raw_limit, "limit")
    except ValueError:
        limit = DEFAULT_LIMIT

    try:
        offset = int(raw_offset)
    except (TypeError, ValueError):
        offset = 0

    if limit > MAX_LIMIT:
        limit = MAX_LIMIT
    if offset < 0:
        offset = 0

    return limit, offset


def _default_subscription() -> Dict[str, Any]:
    """Единый дефолт, если billing ничего не вернул."""
    return {
        "plan_type": "free",
        "is_paid": False,
        "status": "unknown",
        "paid_until": None,
    }


def _serialize_client_for_panel(
    client: TelegramUser,
    subscription: Dict[str, Any],
    status_value: str,
) -> Dict[str, Any]:
    """
    Как именно мы отдаём клиента во фронт панели тренера.
    Делаем в одном месте, чтобы не копипастить.
    """
    return {
        "id": client.id,
        # фронту иногда удобно получать telegram_id строкой (чтобы не ловить баги JS с big int)
        "telegram_id": str(client.telegram_id),
        "first_name": client.first_name or "",
        "last_name": client.last_name or "",
        "username": client.username or "",
        "photo_url": "",  # TODO: добавить поддержку фото
        "status": status_value,  # "new" / "contacted"
        "display_name": client.display_name,
        "ai_test_completed": client.ai_test_completed,
        "details": client.ai_test_answers or {},
        "recommended_calories": client.recommended_calories,
        "recommended_protein": client.recommended_protein,
        "recommended_fat": client.recommended_fat,
        "recommended_carbs": client.recommended_carbs,
        "created_at": client.created_at.isoformat(),
        "subscription": subscription,
        # совместимость со старым фронтом: иногда он ждёт is_paid отдельно
        "is_paid": bool(subscription.get("is_paid", False)),
    }


def _query_applications_qs():
    """
    Базовый queryset "заявки": те, кто прошёл тест.
    Используем only(), чтобы не тащить лишние колонки.
    """
    return (
        TelegramUser.objects.filter(ai_test_completed=True)
        .select_related("user")
        .only(
            "id",
            "telegram_id",
            "first_name",
            "last_name",
            "username",
            "ai_test_completed",
            "ai_test_answers",
            "recommended_calories",
            "recommended_protein",
            "recommended_fat",
            "recommended_carbs",
            "created_at",
            "is_client",
            "user_id",
        )
        .order_by("-created_at")
    )


# ============================================================================
# 1) Applications (все, кто прошёл опрос/тест)
# ============================================================================


@extend_schema(
    tags=["Telegram"],
    summary="Get all clients/applications",
    description="Получить список всех пользователей, прошедших опрос/тест через бота",
    parameters=[
        OpenApiParameter(
            name="limit",
            required=False,
            type=int,
            description="Сколько записей вернуть (default 200, max 1000)",
        ),
        OpenApiParameter(
            name="offset", required=False, type=int, description="Смещение для пагинации"
        ),
    ],
)
@api_view(["GET"])
@permission_classes([TelegramAdminPermission])
def get_applications_api(request):
    """
    GET /api/v1/telegram/applications/

    Возвращает список заявок для панели тренера.
    """
    limit, offset = _get_pagination_params(request)

    qs = _query_applications_qs()
    clients = list(qs[offset : offset + limit])

    # billing: получаем подписки одной пачкой (чтобы не было N+1 запросов)
    user_ids = [c.user_id for c in clients if c.user_id]
    subscriptions_map = get_subscriptions_for_users(user_ids)

    data: List[Dict[str, Any]] = []
    for client in clients:
        subscription = subscriptions_map.get(client.user_id, _default_subscription())
        status_value = "contacted" if client.is_client else "new"
        data.append(_serialize_client_for_panel(client, subscription, status_value))

    return Response(data, status=status.HTTP_200_OK)


# ============================================================================
# 2) Clients list + Promote application -> client
# ============================================================================


@extend_schema(
    tags=["Telegram"],
    summary="Get list of clients / Promote application to client",
    description=(
        "GET: список клиентов (is_client=True)\nPOST: пометить заявку как клиента (is_client=True)"
    ),
    parameters=[
        OpenApiParameter(name="limit", required=False, type=int),
        OpenApiParameter(name="offset", required=False, type=int),
    ],
)
@api_view(["GET", "POST"])
@permission_classes([TelegramAdminPermission])
def clients_list(request):
    """
    GET /api/v1/telegram/clients/
    POST /api/v1/telegram/clients/  body: { "id": <telegram_user_id> }
    """
    if request.method == "GET":
        limit, offset = _get_pagination_params(request)

        qs = _query_applications_qs().filter(is_client=True)
        clients = list(qs[offset : offset + limit])

        user_ids = [c.user_id for c in clients if c.user_id]
        subscriptions_map = get_subscriptions_for_users(user_ids)

        data: List[Dict[str, Any]] = []
        for client in clients:
            subscription = subscriptions_map.get(client.user_id, _default_subscription())
            data.append(_serialize_client_for_panel(client, subscription, status_value="contacted"))

        return Response(data, status=status.HTTP_200_OK)

    # POST: добавить заявку в клиенты
    raw_id = request.data.get("id")
    if raw_id is None:
        return Response({"error": "ID is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        client_id = _safe_int(raw_id, "id")
    except ValueError:
        return Response(
            {"error": "ID must be a positive integer"}, status=status.HTTP_400_BAD_REQUEST
        )

    telegram_user = get_object_or_404(TelegramUser, id=client_id)

    # Минимальная логика безопасности/целостности:
    # - странно делать клиентом того, кто не прошёл тест (но допускаем, если тебе это надо — убери проверку)
    if not telegram_user.ai_test_completed:
        return Response(
            {"error": "User has not completed AI test"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Идемпотентность: если уже клиент — просто возвращаем успех
    if telegram_user.is_client:
        return Response(
            {"status": "success", "message": "Client already added", "id": telegram_user.id},
            status=status.HTTP_200_OK,
        )

    telegram_user.is_client = True
    telegram_user.save(update_fields=["is_client"])

    return Response(
        {"status": "success", "message": "Client added successfully", "id": telegram_user.id},
        status=status.HTTP_200_OK,
    )


# ============================================================================
# 3) Client detail: remove client flag
# ============================================================================


@extend_schema(
    tags=["Telegram"],
    summary="Remove client flag",
    description="Убрать флаг is_client (клиент -> обратно в заявки)",
)
@api_view(["DELETE"])
@permission_classes([TelegramAdminPermission])
def client_detail(request, client_id: int):
    """
    DELETE /api/v1/telegram/clients/{client_id}/
    """
    telegram_user = get_object_or_404(TelegramUser, id=client_id)

    # Идемпотентность: если и так не клиент — просто success
    if not telegram_user.is_client:
        return Response(
            {"status": "success", "message": "Client already removed"},
            status=status.HTTP_200_OK,
        )

    telegram_user.is_client = False
    telegram_user.save(update_fields=["is_client"])

    return Response(
        {"status": "success", "message": "Client removed successfully"},
        status=status.HTTP_200_OK,
    )


# ============================================================================
# 4) Subscribers + revenue stats
# ============================================================================


@extend_schema(
    tags=["Telegram"],
    summary="Get subscribers stats and revenue",
    description="Получить статистику подписчиков и выручки",
)
@api_view(["GET"])
@permission_classes([TelegramAdminPermission])
def get_subscribers_api(request):
    """
    GET /api/v1/telegram/subscribers/

    Возвращаем:
    - subscribers: список пользователей с данными подписки
    - stats: агрегаты (total/free/monthly/yearly/revenue)
    """
    counts = get_subscribers_metrics()
    revenue = get_revenue_metrics()

    # Тут потенциально много пользователей — тоже даём пагинацию
    limit, offset = _get_pagination_params(request)

    qs = (
        TelegramUser.objects.filter(ai_test_completed=True)
        .select_related("user")
        .only("id", "telegram_id", "first_name", "last_name", "username", "created_at", "user_id")
        .order_by("-created_at")
    )

    users = list(qs[offset : offset + limit])

    user_ids = [u.user_id for u in users if u.user_id]
    subscriptions_map = get_subscriptions_for_users(user_ids)

    subscribers: List[Dict[str, Any]] = []
    for u in users:
        subscription = subscriptions_map.get(u.user_id, _default_subscription())
        subscribers.append(
            {
                "id": u.id,
                "telegram_id": u.telegram_id,
                "first_name": u.first_name or "",
                "last_name": u.last_name or "",
                "username": u.username or "",
                "plan_type": subscription.get("plan_type", "free"),
                "subscribed_at": u.created_at.isoformat(),
                "expires_at": subscription.get("paid_until"),
                "is_active": subscription.get("status") == "active",
            }
        )

    stats = {
        "total": int(counts.get("free", 0))
        + int(counts.get("monthly", 0))
        + int(counts.get("yearly", 0)),
        "free": int(counts.get("free", 0)),
        "monthly": int(counts.get("monthly", 0)),
        "yearly": int(counts.get("yearly", 0)),
        "revenue": float(revenue.get("total", 0)),
    }

    return Response({"subscribers": subscribers, "stats": stats}, status=status.HTTP_200_OK)
