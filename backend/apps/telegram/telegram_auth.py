"""
Этот файл отвечает за ДОСТУП через Telegram WebApp.

Если коротко:
— Проверяет, что запрос реально пришёл из Telegram Mini App
— Проверяет, что пользователь — АДМИН (по списку TELEГРАМ ID)
— Закрывает доступ к админке и API для всех остальных

Используется в трёх местах:
1) как декоратор @telegram_admin_required
2) как permission для DRF (TelegramAdminPermission)
3) как middleware для защиты /dj-admin/*
"""

from __future__ import annotations

import logging
from functools import wraps
from typing import Optional, Set

from django.conf import settings
from django.http import HttpResponseForbidden
from django.utils.deprecation import MiddlewareMixin

from apps.telegram.auth.services.webapp_auth import get_webapp_auth_service

logger = logging.getLogger(__name__)

# =========================
# НАСТРОЙКИ БЕЗОПАСНОСТИ
# =========================

# Максимальный размер заголовка X-Telegram-Init-Data
# Нужен, чтобы не убить сервер мусорными запросами
DEFAULT_MAX_INIT_DATA_LEN = 8192
MAX_INIT_DATA_LEN: int = int(
    getattr(settings, "TELEGRAM_INIT_DATA_MAX_LEN", DEFAULT_MAX_INIT_DATA_LEN)
)

# Ключи для кеширования результата на время одного запроса
# Чтобы не проверять initData по 5 раз за один запрос
_REQ_CACHE_FLAG = "_tg_admin_checked"
_REQ_CACHE_ALLOWED = "_tg_admin_allowed"


def _forbidden() -> HttpResponseForbidden:
    """
    Единый ответ «Нет доступа».
    """
    return HttpResponseForbidden("Нет доступа")


def _get_init_data_from_request(request) -> Optional[str]:
    """
    Забираем initData из заголовка запроса.

    Telegram Mini App передаёт его в:
    X-Telegram-Init-Data
    """
    raw = request.headers.get("X-Telegram-Init-Data") or request.META.get(
        "HTTP_X_TELEGRAM_INIT_DATA"
    )

    if not raw:
        return None

    # Защита от слишком большого заголовка
    if len(raw) > MAX_INIT_DATA_LEN:
        # ВАЖНО: не логируем сам initData — там личные данные
        logger.warning("X-Telegram-Init-Data слишком большой: %s байт", len(raw))
        return None

    return raw


def _parse_telegram_admins() -> Set[int]:
    """
    Приводим settings.TELEGRAM_ADMINS к нормальному виду.

    Можно указать:
    TELEGRAM_ADMINS = [123, 456]
    TELEGRAM_ADMINS = "123"
    TELEGRAM_ADMINS = 123
    """
    raw = getattr(settings, "TELEGRAM_ADMINS", None)
    if not raw:
        return set()

    items = raw if isinstance(raw, (list, tuple, set)) else [raw]

    admins: Set[int] = set()
    for item in items:
        try:
            admins.add(int(item))
        except (TypeError, ValueError):
            logger.warning("Некорректный TELEGRAM_ADMINS: %r", item)

    return admins


def _is_telegram_admin(request) -> bool:
    """
    ГЛАВНАЯ ФУНКЦИЯ ФАЙЛА.

    Возвращает True если:
    — запрос пришёл из Telegram WebApp
    — initData валиден (подпись + срок)
    — user_id есть в TELEGRAM_ADMINS
    """

    # Если уже проверяли в этом запросе — возвращаем результат
    if getattr(request, _REQ_CACHE_FLAG, False):
        return bool(getattr(request, _REQ_CACHE_ALLOWED, False))

    setattr(request, _REQ_CACHE_FLAG, True)

    raw_init_data = _get_init_data_from_request(request)
    if not raw_init_data:
        setattr(request, _REQ_CACHE_ALLOWED, False)
        return False

    auth_service = get_webapp_auth_service()

    # Проверяем подпись и целостность данных
    try:
        parsed = auth_service.validate_init_data(raw_init_data)
    except Exception:
        # Любая ошибка = отказ в доступе
        logger.exception("Ошибка проверки Telegram initData")
        setattr(request, _REQ_CACHE_ALLOWED, False)
        return False

    if not parsed:
        setattr(request, _REQ_CACHE_ALLOWED, False)
        return False

    # Достаём Telegram user_id
    try:
        user_id = auth_service.get_user_id_from_init_data(parsed)
    except Exception:
        logger.exception("Ошибка чтения user_id из initData")
        setattr(request, _REQ_CACHE_ALLOWED, False)
        return False

    admins = _parse_telegram_admins()
    allowed = bool(user_id is not None and user_id in admins)

    setattr(request, _REQ_CACHE_ALLOWED, allowed)

    # Если доступ разрешён — кладём данные в request
    # чтобы использовать дальше во вьюхах
    if allowed:
        request.telegram_init_data = parsed
        request.telegram_user_id = user_id

    return allowed


def telegram_admin_required(view_func):
    """
    Декоратор для обычных Django view.

    Использование:
    @telegram_admin_required
    def my_view(request):
        ...
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not _is_telegram_admin(request):
            return _forbidden()
        return view_func(request, *args, **kwargs)

    return _wrapped


class TelegramAdminOnlyMiddleware(MiddlewareMixin):
    """
    Middleware для защиты Django-админки (/dj-admin/*).

    Пускает ТОЛЬКО:
    — Django staff / superuser по сессии
    — Telegram админа через WebApp
    """

    protected_prefixes = ("/dj-admin", "/dj-admin/")

    def process_request(self, request):
        path = request.path or "/"

        # Страницу логина админки нельзя блокировать
        if path.rstrip("/") == "/dj-admin/login":
            return None

        if path.startswith(self.protected_prefixes):
            # Если пользователь вошёл через Django админку
            user = getattr(request, "user", None)
            if user and user.is_authenticated and (user.is_staff or user.is_superuser):
                return None

            # Во всех остальных случаях — только Telegram админ
            if not _is_telegram_admin(request):
                return _forbidden()

        return None


# =========================
# DRF PERMISSION
# =========================

try:
    from rest_framework.permissions import BasePermission
except Exception:
    BasePermission = object  # если DRF не установлен


class TelegramAdminPermission(BasePermission):
    """
    Permission для DRF API.

    Использование:
    permission_classes = [TelegramAdminPermission]
    """
    message = "Нет доступа"

    def has_permission(self, request, view):
        return _is_telegram_admin(request)
