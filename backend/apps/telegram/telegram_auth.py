"""Utilities for validating Telegram WebApp initData and restricting admin access."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from functools import wraps
from typing import Dict, Optional
from urllib.parse import parse_qsl

from django.conf import settings
from django.http import HttpResponseForbidden
from django.utils.deprecation import MiddlewareMixin

try:
    from rest_framework.permissions import BasePermission
except Exception:  # pragma: no cover - DRF may not be installed in some contexts
    class BasePermission:  # type: ignore
        message = "Нет доступа"

        def has_permission(self, request, view):  # pragma: no cover - fallback
            return False


def _forbidden_response():
    return HttpResponseForbidden("Нет доступа")


def validate_init_data(
    raw_init_data: str,
    bot_token: str,
    *,
    max_age_seconds: int = 86400,
) -> Optional[Dict[str, str]]:
    """
    Validate Telegram WebApp initData signature according to official docs.

    Args:
        raw_init_data: Raw query-string formatted initData from Telegram.WebApp.initData
        bot_token: Bot token stored in settings.TELEGRAM_BOT_TOKEN

    Returns:
        Parsed initData dict without the ``hash`` key if signature is valid, else ``None``.
    """

    if not raw_init_data or not bot_token:
        return None

    parsed_data = dict(parse_qsl(raw_init_data, keep_blank_values=True))

    received_hash = parsed_data.pop("hash", None)
    if not received_hash:
        return None

    if max_age_seconds:
        try:
            auth_date = int(parsed_data.get("auth_date", "0"))
            if auth_date and time.time() - auth_date > max_age_seconds:
                return None
        except (TypeError, ValueError):
            return None

    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(parsed_data.items(), key=lambda item: item[0])
    )

    secret_key = hashlib.sha256(bot_token.encode()).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        return None

    return parsed_data


def get_user_id_from_init_data(data: Dict[str, str]) -> Optional[int]:
    """Extract Telegram user id from parsed initData dict."""

    user_json = data.get("user")
    if not user_json:
        return None

    try:
        user_data = json.loads(user_json)
        return int(user_data.get("id"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _get_raw_init_data(request) -> Optional[str]:
    return request.META.get("HTTP_X_TG_INIT_DATA") or request.headers.get("X-TG-INIT-DATA")


def _is_telegram_admin(request) -> bool:
    raw_init_data = _get_raw_init_data(request)
    parsed_data = validate_init_data(raw_init_data, settings.TELEGRAM_BOT_TOKEN)
    if not parsed_data:
        return False

    user_id = get_user_id_from_init_data(parsed_data)
    raw_admins = getattr(settings, "TELEGRAM_ADMINS", set()) or set()
    if isinstance(raw_admins, (list, tuple, set)):
        admins = {int(admin) for admin in raw_admins}
    else:
        admins = {int(raw_admins)} if raw_admins else set()

    if user_id is None or user_id not in admins:
        return False

    request.telegram_init_data = parsed_data
    request.telegram_user_id = user_id
    return True


def telegram_admin_required(view_func):
    """Decorator to allow access only to configured Telegram admins."""

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not _is_telegram_admin(request):
            return _forbidden_response()
        return view_func(request, *args, **kwargs)

    return _wrapped_view


class TelegramAdminOnlyMiddleware(MiddlewareMixin):
    """Middleware to restrict Django admin endpoints to Telegram WebApp admins only."""

    protected_prefixes = ("/admin/", "/admin")

    def process_request(self, request):  # noqa: D401 - middleware hook
        path = request.path.rstrip("/") or "/"
        if any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in self.protected_prefixes):
            if request.method in {"GET", "HEAD"}:
                return None
            if not _is_telegram_admin(request):
                return _forbidden_response()
        return None


class TelegramAdminPermission(BasePermission):
    """DRF permission enforcing Telegram WebApp admin validation."""

    message = "Нет доступа"

    def has_permission(self, request, view):  # type: ignore[override]
        return _is_telegram_admin(request)
