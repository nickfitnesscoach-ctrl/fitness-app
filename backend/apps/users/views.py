"""
apps/users/views.py

Профиль пользователя:
- Все ручки требуют IsAuthenticated (аутентификация Telegram WebApp).
- Логи — безопасные (не пишем request.data целиком).
"""

from __future__ import annotations

import logging

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.audit import SecurityAuditLogger

from .models import Profile
from .serializers import ProfileSerializer, UserSerializer
from .throttles import ProfileUpdateThrottle

logger = logging.getLogger(__name__)


from django.conf import settings  # Added import


@extend_schema(tags=["Profile"])
@extend_schema_view(
    get=extend_schema(
        summary="Получить профиль текущего пользователя",
        description="Возвращает информацию о профиле авторизованного пользователя.",
        responses={200: UserSerializer},
    ),
    put=extend_schema(
        summary="Обновить профиль полностью",
        description="Полное обновление профиля пользователя.",
        request=ProfileSerializer,
        responses={200: UserSerializer},
    ),
    patch=extend_schema(
        summary="Частично обновить профиль",
        description="Частичное обновление полей профиля пользователя.",
        request=ProfileSerializer,
        responses={200: UserSerializer},
    ),
)
class ProfileView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer
    throttle_classes = [ProfileUpdateThrottle]

    def get_throttles(self):
        """
        Custom throttling logic:
        - Disable throttling for GET requests (safe method).
        - Disable throttling in DEV environment to prevent 429 during development.
        """
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return []

        if settings.APP_ENV == "dev":
            return []

        return super().get_throttles()

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        user = self.get_object()

        # Безопасный лог: только ключи, без значений
        fields = list(request.data.keys())
        logger.info(
            "[ProfileView] %s user_id=%s fields=%s",
            "PATCH" if partial else "PUT",
            user.id,
            fields,
        )

        # profile гарантируем
        profile, _ = Profile.objects.get_or_create(user=user)

        profile_serializer = ProfileSerializer(
            profile, data=request.data, partial=partial, context={"request": request}
        )
        profile_serializer.is_valid(raise_exception=True)
        profile_serializer.save()

        user_serializer = self.get_serializer(user)
        return Response(user_serializer.data, status=status.HTTP_200_OK)


@extend_schema(tags=["Profile"])
@extend_schema_view(
    delete=extend_schema(
        summary="Удалить аккаунт",
        description="Удаление аккаунта текущего пользователя.",
        responses={
            204: {"description": "Аккаунт успешно удален"},
            401: {"description": "Не авторизован"},
        },
    )
)
class DeleteAccountView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        user = request.user

        # SECURITY: логируем удаление
        SecurityAuditLogger.log_account_deletion(user, request)

        user.delete()

        # 204 должен быть без тела
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Profile"])
@extend_schema_view(
    post=extend_schema(
        summary="Загрузить/обновить аватар профиля",
        description="Загрузка или обновление аватара текущего пользователя.",
        responses={
            200: UserSerializer,
            400: {"description": "Неверный формат файла или слишком большой размер"},
            401: {"description": "Не авторизован"},
        },
    )
)
class UploadAvatarView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ProfileUpdateThrottle]

    def post(self, request):
        from django.core.exceptions import ValidationError as DjangoValidationError

        from .validators import (
            convert_heic_to_jpeg,
            is_heic_file,
            validate_avatar_file_extension,
            validate_avatar_file_size,
            validate_avatar_mime_type,
        )

        avatar_file = request.FILES.get("avatar")
        if not avatar_file:
            return Response(
                {
                    "code": "avatar_missing",
                    "detail": "Файл аватара не предоставлен. Используйте поле 'avatar'.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            if is_heic_file(avatar_file):
                logger.info("Converting HEIC avatar for user %s", request.user.id)
                avatar_file = convert_heic_to_jpeg(avatar_file)

            validate_avatar_mime_type(avatar_file)
            validate_avatar_file_size(avatar_file)
            validate_avatar_file_extension(avatar_file)

        except DjangoValidationError as e:
            error_message = str(e.message) if hasattr(e, "message") else str(e)
            error_code = e.code if hasattr(e, "code") else "validation_error"
            logger.warning("Avatar validation failed user=%s code=%s", request.user.id, error_code)
            return Response(
                {"code": error_code, "detail": error_message},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        profile, _ = Profile.objects.get_or_create(user=user)

        try:
            profile.set_avatar(avatar_file)
            logger.info("Avatar uploaded user=%s version=%s", user.id, profile.avatar_version)
        except Exception:
            logger.exception("Avatar upload failed user=%s", user.id)
            return Response(
                {
                    "code": "avatar_upload_failed",
                    "detail": "Не удалось загрузить аватар. Попробуйте позже.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        user_serializer = UserSerializer(user, context={"request": request})
        return Response(user_serializer.data, status=status.HTTP_200_OK)
