"""
Telegram WebApp authentication backends.

Зачем этот файл:
- DRF "authentication backends" — это куски кода, которые определяют:
  "кто делает запрос" и "можно ли этому человеку доверять".

Здесь 3 режима (и только так):
1) TelegramWebAppAuthentication (PROD и основной)
   - проверяет подпись initData от Telegram Mini App
   - это правильный и безопасный путь

2) DebugModeAuthentication (ТОЛЬКО DEV)
   - нужен, чтобы разрабатывать фронт без Telegram
   - в PROD выключен железно

3) TelegramHeaderAuthentication (ОПЦИОНАЛЬНО)
   - доверяет заголовкам, которые поставил Nginx/прокси
   - по умолчанию ВЫКЛЮЧЕН, потому что это потенциальная дыра,
     если кто-то сможет слать запросы напрямую к backend без Nginx.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Dict, Optional, Tuple

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import authentication, exceptions

from apps.telegram.auth.services.webapp_auth import get_webapp_auth_service
from apps.telegram.models import TelegramUser
from apps.users.models import Profile

User = get_user_model()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Общие хелперы
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class TelegramIdentity:
    """Нормализованные данные, которые мы извлекли из Telegram."""
    telegram_id: int
    username: str = ""
    first_name: str = ""
    last_name: str = ""
    language_code: str = "ru"
    is_premium: bool = False


def _is_dev_debug_allowed() -> bool:
    """
    Разрешаем debug-auth только в DEV.

    В PROD (DEBUG=False) debug режим ДОЛЖЕН быть выключен.
    Дополнительно можно включать флагом WEBAPP_DEBUG_MODE_ENABLED,
    но он имеет смысл только если DEBUG=True.
    """
    if not getattr(settings, "DEBUG", False):
        return False
    return bool(getattr(settings, "WEBAPP_DEBUG_MODE_ENABLED", True))


def _get_header(request, name: str) -> str:
    """Безопасно достать заголовок (DRF/Django разные способы)."""
    # Django превращает заголовки в HTTP_X_...
    meta_key = "HTTP_" + name.upper().replace("-", "_")
    return (request.META.get(meta_key) or request.headers.get(name) or "").strip()


def _parse_int(value: str, field_name: str) -> int:
    """Перевод в int с нормальной ошибкой."""
    try:
        x = int(value)
    except (ValueError, TypeError):
        raise exceptions.AuthenticationFailed(f"Invalid {field_name}")
    if x <= 0:
        raise exceptions.AuthenticationFailed(f"Invalid {field_name}")
    return x


def _ensure_user_and_profiles(identity: TelegramIdentity) -> User:
    """
    SSOT логика создания пользователя:
    - TelegramUser хранит telegram_id и данные
    - Django User — основной пользователь для приложения
    - Profile обязателен (у тебя он используется в webapp_auth/view)
    """
    telegram_id = identity.telegram_id
    django_username = f"tg_{telegram_id}"

    with transaction.atomic():
        try:
            tg = TelegramUser.objects.select_related("user").get(telegram_id=telegram_id)
            user = tg.user
        except TelegramUser.DoesNotExist:
            # создаём Django user, если его нет
            user, _ = User.objects.get_or_create(
                username=django_username,
                defaults={
                    "email": f"tg{telegram_id}@telegram.user",
                    "first_name": identity.first_name[:150],
                    "last_name": identity.last_name[:150],
                },
            )
            # на всякий: пароль не нужен, вход только через Telegram
            try:
                user.set_unusable_password()
                user.save(update_fields=["password"])
            except Exception:
                # не критично
                pass

            tg = TelegramUser.objects.create(
                user=user,
                telegram_id=telegram_id,
                username=identity.username or "",
                first_name=identity.first_name or "",
                last_name=identity.last_name or "",
                language_code=identity.language_code or "ru",
                is_premium=bool(identity.is_premium),
            )

        # обновляем данные при каждом логине (это нормально)
        changed = False
        if tg.username != (identity.username or ""):
            tg.username = identity.username or ""
            changed = True
        if tg.first_name != (identity.first_name or ""):
            tg.first_name = identity.first_name or ""
            changed = True
        if tg.last_name != (identity.last_name or ""):
            tg.last_name = identity.last_name or ""
            changed = True
        if tg.language_code != (identity.language_code or "ru"):
            tg.language_code = identity.language_code or "ru"
            changed = True
        if tg.is_premium != bool(identity.is_premium):
            tg.is_premium = bool(identity.is_premium)
            changed = True

        if changed:
            tg.save()

        # гарантируем Profile
        Profile.objects.get_or_create(user=user)

    return user


# ---------------------------------------------------------------------
# 1) DebugModeAuthentication — только DEV
# ---------------------------------------------------------------------

class DebugModeAuthentication(authentication.BaseAuthentication):
    """
    DEV-only аутентификация для разработки без Telegram.

    Как включается:
    - settings.DEBUG == True
    - settings.WEBAPP_DEBUG_MODE_ENABLED == True (по умолчанию True в DEV)
    - заголовок: X-Debug-Mode: true

    Опционально можно указать:
    - X-Debug-User-Id: 999999999 (или любой int)
    - X-Telegram-First-Name / X-Telegram-Last-Name / X-Telegram-Username
    """

    DEFAULT_DEBUG_USER_ID = 999999999

    def authenticate(self, request) -> Optional[Tuple[User, Dict[str, Any]]]:
        debug_mode = _get_header(request, "X-Debug-Mode").lower()
        if debug_mode != "true":
            return None

        if not _is_dev_debug_allowed():
            # В PROD всегда отрублено. Важно: не "None", а явный fail.
            raise exceptions.AuthenticationFailed("Debug mode is disabled")

        raw_id = _get_header(request, "X-Debug-User-Id") or str(self.DEFAULT_DEBUG_USER_ID)
        telegram_id = _parse_int(raw_id, "debug_user_id")

        identity = TelegramIdentity(
            telegram_id=telegram_id,
            first_name=_get_header(request, "X-Telegram-First-Name") or "Debug",
            last_name=_get_header(request, "X-Telegram-Last-Name") or "User",
            username=_get_header(request, "X-Telegram-Username") or "eatfit24_debug",
            language_code=_get_header(request, "X-Telegram-Language-Code") or "ru",
            is_premium=False,
        )

        user = _ensure_user_and_profiles(identity)

        # логируем без персональных деталей (только факт)
        logger.warning("[SECURITY] DebugModeAuthentication used (DEV only). path=%s", request.path)

        return user, {"auth": "debug"}

    def authenticate_header(self, request) -> str:
        return 'DebugMode realm="api"'


# ---------------------------------------------------------------------
# 2) TelegramWebAppAuthentication — основной безопасный путь
# ---------------------------------------------------------------------

class TelegramWebAppAuthentication(authentication.BaseAuthentication):
    """
    Основной способ: проверяем initData от Telegram Mini App.

    Где ищем initData:
    - заголовок X-Telegram-Init-Data
    - тело запроса (initData / init_data) для POST/PUT/PATCH
    """

    def authenticate(self, request) -> Optional[Tuple[User, Dict[str, Any]]]:
        init_data = _get_header(request, "X-Telegram-Init-Data")
        if not init_data and request.method in {"POST", "PUT", "PATCH"}:
            init_data = (request.data.get("initData") or request.data.get("init_data") or "").strip()

        if not init_data:
            return None

        auth_service = get_webapp_auth_service()
        parsed = auth_service.validate_init_data(init_data)
        if not parsed:
            raise exceptions.AuthenticationFailed("Invalid Telegram initData signature")

        user_data = auth_service.get_user_data_from_init_data(parsed)
        if not user_data:
            raise exceptions.AuthenticationFailed("Invalid Telegram user data")

        telegram_id = user_data.get("id")
        if not telegram_id:
            raise exceptions.AuthenticationFailed("Telegram ID is required")

        identity = TelegramIdentity(
            telegram_id=int(telegram_id),
            first_name=user_data.get("first_name", "") or "",
            last_name=user_data.get("last_name", "") or "",
            username=user_data.get("username", "") or "",
            language_code=user_data.get("language_code", "ru") or "ru",
            is_premium=bool(user_data.get("is_premium", False)),
        )

        user = _ensure_user_and_profiles(identity)
        return user, {"auth": "telegram_webapp"}


# ---------------------------------------------------------------------
# 3) TelegramHeaderAuthentication — опционально, выключено по умолчанию
# ---------------------------------------------------------------------

class TelegramHeaderAuthentication(authentication.BaseAuthentication):
    """
    ОПЦИОНАЛЬНЫЙ режим: доверяем заголовкам X-Telegram-Id и т.п.

    Важно:
    - это безопасно только если backend НЕ доступен напрямую из интернета,
      а все запросы идут через Nginx, который сам валидирует initData.
    - поэтому этот режим ВЫКЛЮЧЕН по умолчанию.

    Включение:
      settings.TELEGRAM_HEADER_AUTH_ENABLED = True
    """

    def authenticate(self, request) -> Optional[Tuple[User, Dict[str, Any]]]:
        if not bool(getattr(settings, "TELEGRAM_HEADER_AUTH_ENABLED", False)):
            return None

        telegram_id_raw = _get_header(request, "X-Telegram-Id")
        if not telegram_id_raw:
            return None

        telegram_id = _parse_int(telegram_id_raw, "telegram_id")

        identity = TelegramIdentity(
            telegram_id=telegram_id,
            first_name=_get_header(request, "X-Telegram-First-Name") or "",
            last_name=_get_header(request, "X-Telegram-Last-Name") or "",
            username=_get_header(request, "X-Telegram-Username") or "",
            language_code=_get_header(request, "X-Telegram-Language-Code") or "ru",
            is_premium=False,
        )

        user = _ensure_user_and_profiles(identity)
        return user, {"auth": "telegram_headers"}

    def authenticate_header(self, request) -> str:
        return 'TelegramHeader realm="api"'
