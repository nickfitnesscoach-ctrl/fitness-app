"""
Authentication views for Telegram integration.
"""

import logging

from django.conf import settings
from django.http import JsonResponse
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from apps.telegram.authentication import TelegramWebAppAuthentication, DebugModeAuthentication
from apps.telegram.telegram_auth import telegram_admin_required
from apps.telegram.services.webapp_auth import get_webapp_auth_service
from apps.telegram.models import TelegramUser
from apps.telegram.serializers import (
    TelegramAuthSerializer,
    TelegramUserSerializer,
    WebAppAuthResponseSerializer,
)
from apps.nutrition.models import DailyGoal
from apps.users.models import Profile

logger = logging.getLogger(__name__)


@telegram_admin_required
def trainer_admin_panel(request):
    """Simple admin panel endpoint protected by Telegram WebApp validation."""
    return JsonResponse({"ok": True, "section": "trainer_panel", "user_id": request.telegram_user_id})


@extend_schema(tags=["TrainerPanel"])
@api_view(["POST"])
@permission_classes([AllowAny])
def trainer_panel_auth(request):
    """Validate Telegram WebApp initData and ensure the user is an admin."""
    logger.info("[TrainerPanel] Auth request started")

    raw_init_data = (
        request.data.get("init_data")
        or request.data.get("initData")
        or request.headers.get("X-Telegram-Init-Data")
    )

    if not raw_init_data:
        logger.warning("[TrainerPanel] No initData in request")
        return Response({"detail": "Нет доступа"}, status=status.HTTP_403_FORBIDDEN)

    logger.info("[TrainerPanel] initData length: %d", len(raw_init_data))

    auth_service = get_webapp_auth_service()
    parsed_data = auth_service.validate_init_data(raw_init_data)

    if not parsed_data:
        logger.warning("[TrainerPanel] initData validation failed")
        return Response({"detail": "Нет доступа"}, status=status.HTTP_403_FORBIDDEN)

    logger.info("[TrainerPanel] initData validation successful")

    user_id = auth_service.get_user_id_from_init_data(parsed_data)
    if not user_id:
        logger.error("[TrainerPanel] Failed to extract user_id")
        return Response({"detail": "Нет доступа"}, status=status.HTTP_403_FORBIDDEN)

    logger.info("[TrainerPanel] Extracted user_id: %s", user_id)

    admins = settings.TELEGRAM_ADMINS

    if not admins:
        logger.warning("[TrainerPanel] Admin list empty, allowing access (DEV mode?)")
        return Response({
            "ok": True,
            "user_id": user_id,
            "role": "admin",
            "warning": "admin_list_empty"
        })

    if user_id not in admins:
        logger.warning(
            "[TrainerPanel] Access denied for user_id=%s (admins: %s)",
            user_id, admins
        )
        return Response({"detail": "Нет доступа"}, status=status.HTTP_403_FORBIDDEN)

    logger.info("[TrainerPanel] Access granted for user_id=%s", user_id)
    return Response({
        "ok": True,
        "user_id": user_id,
        "role": "admin"
    })


@extend_schema(tags=['Telegram'])
@api_view(['POST'])
@permission_classes([AllowAny])
def telegram_auth(request):
    """
    Аутентификация через Telegram Mini App.

    POST /api/v1/telegram/auth/
    """
    authenticator = TelegramWebAppAuthentication()

    try:
        user, _ = authenticator.authenticate(request)

        if not user:
            return Response(
                {"error": "Authentication failed"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        refresh = RefreshToken.for_user(user)
        telegram_user = user.telegram_profile

        telegram_admins = getattr(settings, 'TELEGRAM_ADMINS', set())
        is_admin = telegram_user.telegram_id in telegram_admins

        serializer = TelegramAuthSerializer({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': telegram_user,
            'is_admin': is_admin
        })

        return Response(serializer.data)

    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@extend_schema(tags=['Telegram'])
@api_view(['POST'])
@permission_classes([AllowAny])
def webapp_auth(request):
    """
    Единый endpoint для авторизации Telegram WebApp.
    Также поддерживает Browser Debug Mode (X-Debug-Mode: true).

    POST /api/v1/telegram/webapp/auth/
    """
    # Try Debug Mode authentication first
    debug_auth = DebugModeAuthentication()
    result = debug_auth.authenticate(request)
    
    if result:
        logger.info("[WebAppAuth] Using Debug Mode authentication")
    else:
        # Fall back to normal Telegram WebApp authentication
        authenticator = TelegramWebAppAuthentication()
        result = authenticator.authenticate(request)

    try:
        if not result:
            logger.warning("[WebAppAuth] Authentication failed: no result from authenticator")
            return Response(
                {"error": "Authentication failed"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        user, auth_data = result

        if not user:
            logger.warning("[WebAppAuth] Authentication failed: no user")
            return Response(
                {"error": "Authentication failed"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        logger.info(f"[WebAppAuth] User authenticated: {user.id} (username: {user.username})")

        try:
            telegram_user = user.telegram_profile
        except TelegramUser.DoesNotExist:
            logger.warning(f"[WebAppAuth] User {user.id} without TelegramUser, attempting to create")
            telegram_id = getattr(request, 'telegram_id', None)
            if not telegram_id and hasattr(user, 'profile') and user.profile.telegram_id:
                telegram_id = user.profile.telegram_id

            if telegram_id:
                telegram_user = TelegramUser.objects.create(
                    user=user,
                    telegram_id=telegram_id,
                    username=user.username.replace('tg_', '') if user.username.startswith('tg_') else '',
                    first_name=user.first_name,
                    last_name=user.last_name,
                )
                logger.info(f"[WebAppAuth] Created TelegramUser {telegram_id} for user {user.id}")
            else:
                logger.error(f"[WebAppAuth] Cannot create TelegramUser for user {user.id}: no telegram_id")
                return Response(
                    {"error": "Telegram profile creation failed"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        profile, created = Profile.objects.get_or_create(user=user)
        if created:
            logger.info(f"[WebAppAuth] Created empty Profile for user {user.id}")

        active_goal = (
            DailyGoal.objects
            .filter(user=user, is_active=True)
            .order_by('-created_at')
            .first()
        )

        admin_ids = set()
        telegram_admins = getattr(settings, 'TELEGRAM_ADMINS', '')
        if telegram_admins:
            try:
                if isinstance(telegram_admins, str):
                    admin_ids.update(
                        int(x.strip())
                        for x in telegram_admins.split(',')
                        if x.strip().isdigit()
                    )
                elif isinstance(telegram_admins, (set, list)):
                    admin_ids.update(int(x) for x in telegram_admins)
            except (ValueError, AttributeError) as e:
                logger.warning(f"[WebAppAuth] Failed to parse TELEGRAM_ADMINS: {e}")

        bot_admin_id = getattr(settings, 'BOT_ADMIN_ID', None)
        if bot_admin_id:
            try:
                admin_ids.add(int(bot_admin_id))
            except (ValueError, TypeError) as e:
                logger.warning(f"[WebAppAuth] Failed to parse BOT_ADMIN_ID: {e}")

        is_admin = telegram_user.telegram_id in admin_ids
        logger.info(f"[WebAppAuth] User {user.id} admin status: {is_admin}")

        response_data = {
            'user': {
                'id': user.id,
                'telegram_id': telegram_user.telegram_id,
                'username': telegram_user.username or '',
                'first_name': telegram_user.first_name or '',
                'last_name': telegram_user.last_name or '',
            },
            'profile': profile,
            'goals': active_goal,
            'is_admin': is_admin,
        }

        serializer = WebAppAuthResponseSerializer(response_data)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        logger.exception(f"[WebAppAuth] Unexpected error: {e}")
        return Response(
            {"error": "Internal server error"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(tags=['Telegram'])
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def telegram_profile(request):
    """
    Получить Telegram профиль текущего пользователя.

    GET /api/v1/telegram/profile/
    """
    try:
        telegram_user = request.user.telegram_profile
        serializer = TelegramUserSerializer(telegram_user)
        return Response(serializer.data)

    except TelegramUser.DoesNotExist:
        return Response(
            {"error": "Telegram profile not found"},
            status=status.HTTP_404_NOT_FOUND
        )
