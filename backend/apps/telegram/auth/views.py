"""
Authentication views for Telegram integration.

Зачем этот файл:
- Здесь вся авторизация, связанная с Telegram:
  1) Telegram Mini App (WebApp initData)
  2) Trainer Panel (только для админов)
  3) JWT-токены для backend API
- Это КРИТИЧЕСКАЯ зона безопасности.
  Любая ошибка здесь = утечка доступа.

Принципы:
- В PROD никаких "если список админов пустой — пускаем"
- Debug-режим работает ТОЛЬКО при settings.DEBUG=True
- Клиенту никогда не возвращаем детали ошибок
"""

from __future__ import annotations

import logging
from typing import Set

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from apps.nutrition.models import DailyGoal
from apps.telegram.auth.authentication import (
    DebugModeAuthentication,
    TelegramWebAppAuthentication,
)
from apps.telegram.auth.services.webapp_auth import get_webapp_auth_service
from apps.telegram.models import TelegramUser
from apps.telegram.serializers import (
    TelegramAuthSerializer,
    TelegramUserSerializer,
    WebAppAuthResponseSerializer,
)
from apps.users.models import Profile

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------

def _forbidden() -> Response:
    """Единый ответ 403 без утечек информации."""
    return Response({"detail": "Нет доступа"}, status=status.HTTP_403_FORBIDDEN)


def _parse_admin_ids() -> Set[int]:
    """
    Приводим TELEGRAM_ADMINS к set[int].

    Допустимые форматы в settings:
    - set / list / tuple[int]
    - строка "123,456"
    """
    raw = getattr(settings, "TELEGRAM_ADMINS", None)
    result: Set[int] = set()

    if not raw:
        return result

    try:
        if isinstance(raw, str):
            for x in raw.split(","):
                if x.strip().isdigit():
                    result.add(int(x.strip()))
        elif isinstance(raw, (set, list, tuple)):
            result.update(int(x) for x in raw)
    except Exception:
        logger.warning("Failed to parse TELEGRAM_ADMINS")

    return result


def _is_debug_allowed() -> bool:
    """
    DebugModeAuthentication разрешён ТОЛЬКО в DEBUG.
    Никаких debug-флагов в проде.
    """
    return bool(getattr(settings, "DEBUG", False))


# ---------------------------------------------------------------------
# Trainer Panel (админка)
# ---------------------------------------------------------------------

@api_view(["POST"])
@permission_classes([AllowAny])
def trainer_panel_auth(request):
    """
    Авторизация Trainer Panel через Telegram WebApp.

    Условия доступа:
    - валидный Telegram initData
    - telegram_id ∈ TELEGRAM_ADMINS
    - если список админов пустой:
        - DEV (DEBUG=True) → доступ
        - PROD → 403
    """
    raw_init_data = (
        request.data.get("init_data")
        or request.data.get("initData")
        or request.headers.get("X-Telegram-Init-Data")
    )

    if not raw_init_data:
        return _forbidden()

    auth_service = get_webapp_auth_service()
    parsed = auth_service.validate_init_data(raw_init_data)

    if not parsed:
        return _forbidden()

    telegram_id = auth_service.get_user_id_from_init_data(parsed)
    if not telegram_id:
        return _forbidden()

    admin_ids = _parse_admin_ids()

    # Если админы не заданы
    if not admin_ids:
        if not settings.DEBUG:
            logger.error("TELEGRAM_ADMINS is empty in PROD")
            return _forbidden()

        # DEV-режим
        logger.warning("Trainer panel access allowed in DEBUG mode")
        return Response({"ok": True, "role": "admin", "debug": True})

    if telegram_id not in admin_ids:
        return _forbidden()

    return Response({"ok": True, "role": "admin"})


# ---------------------------------------------------------------------
# Telegram Mini App → JWT
# ---------------------------------------------------------------------

@extend_schema(tags=["Telegram"])
@api_view(["POST"])
@permission_classes([AllowAny])
def telegram_auth(request):
    """
    Аутентификация Telegram Mini App → JWT.

    POST /api/v1/telegram/auth/

    Используется, когда Mini App общается с backend API.
    """
    authenticator = TelegramWebAppAuthentication()

    try:
        # Debug auth check
        if _is_debug_allowed():
            debug_auth = DebugModeAuthentication()
            result = debug_auth.authenticate(request)
            if result:
                return Response(TelegramAuthSerializer({
                    "access": "debug_access_token", # Mock token or generated one
                    "refresh": "debug_refresh_token",
                    "user": result[0].telegram_profile,
                    "is_admin": True,
                }).data, status=status.HTTP_200_OK)

        result = authenticator.authenticate(request)
        if not result:
            return Response({"error": "Authentication failed"}, status=status.HTTP_401_UNAUTHORIZED)

        user, _ = result
        if not user:
            return Response({"error": "Authentication failed"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            telegram_user = user.telegram_profile
        except TelegramUser.DoesNotExist:
            return Response({"error": "Telegram profile not found"}, status=status.HTTP_404_NOT_FOUND)

        refresh = RefreshToken.for_user(user)

        admin_ids = _parse_admin_ids()
        is_admin = telegram_user.telegram_id in admin_ids

        serializer = TelegramAuthSerializer({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": telegram_user,
            "is_admin": is_admin,
        })

        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception:
        logger.exception("telegram_auth failed")
        return Response({"error": "Authentication failed"}, status=status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------
# Unified WebApp Auth (Mini App + Trainer Panel)
# ---------------------------------------------------------------------

@extend_schema(tags=["Telegram"])
@api_view(["POST"])
@permission_classes([AllowAny])
def webapp_auth(request):
    """
    Универсальная авторизация Telegram WebApp.

    - В DEV: допускается DebugModeAuthentication
    - В PROD: ТОЛЬКО Telegram initData
    """
    result = None

    # Debug auth — только в DEBUG
    if _is_debug_allowed():
        debug_auth = DebugModeAuthentication()
        result = debug_auth.authenticate(request)

    if not result:
        authenticator = TelegramWebAppAuthentication()
        result = authenticator.authenticate(request)

    if not result:
        return Response({"error": "Authentication failed"}, status=status.HTTP_401_UNAUTHORIZED)

    user, _ = result
    if not user:
        return Response({"error": "Authentication failed"}, status=status.HTTP_401_UNAUTHORIZED)

    # TelegramUser
    telegram_user, _ = TelegramUser.objects.get_or_create(
        user=user,
        defaults={
            "telegram_id": getattr(request, "telegram_id", None),
            "username": "",
            "first_name": user.first_name,
            "last_name": user.last_name,
        }
    )

    # Profile
    profile, _ = Profile.objects.get_or_create(user=user)

    # Active goals
    active_goal = (
        DailyGoal.objects
        .filter(user=user, is_active=True)
        .order_by("-created_at")
        .first()
    )

    admin_ids = _parse_admin_ids()
    is_admin = telegram_user.telegram_id in admin_ids

    serializer = WebAppAuthResponseSerializer({
        "user": {
            "id": user.id,
            "telegram_id": telegram_user.telegram_id,
            "username": telegram_user.username or "",
            "first_name": telegram_user.first_name or "",
            "last_name": telegram_user.last_name or "",
        },
        "profile": profile,
        "goals": active_goal,
        "is_admin": is_admin,
    })

    return Response(serializer.data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------

@extend_schema(tags=["Telegram"])
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def telegram_profile(request):
    """
    Получить Telegram профиль текущего пользователя.
    Требует JWT.
    """
    try:
        telegram_user = request.user.telegram_profile
    except TelegramUser.DoesNotExist:
        return Response({"error": "Telegram profile not found"}, status=status.HTTP_404_NOT_FOUND)

    serializer = TelegramUserSerializer(telegram_user)
    return Response(serializer.data, status=status.HTTP_200_OK)
