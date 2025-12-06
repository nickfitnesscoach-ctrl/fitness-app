"""Utilities for validating Telegram WebApp initData and restricting admin access."""

from __future__ import annotations

import logging
from functools import wraps
from typing import Dict, Optional

from django.conf import settings
from django.http import HttpResponseForbidden
from django.utils.deprecation import MiddlewareMixin

from .services.webapp_auth import get_webapp_auth_service

try:
    from rest_framework.permissions import BasePermission
except Exception:  # pragma: no cover - DRF may not be installed in some contexts
    class BasePermission:  # type: ignore
        message = "Нет доступа"

        def has_permission(self, request, view):  # pragma: no cover - fallback
            return False


logger = logging.getLogger(__name__)


def _forbidden_response():
    return HttpResponseForbidden("Нет доступа")


def _get_raw_init_data(request) -> Optional[str]:
    return request.META.get("HTTP_X_TG_INIT_DATA") or request.headers.get("X-TG-INIT-DATA")


def _is_telegram_admin(request) -> bool:
    raw_init_data = _get_raw_init_data(request)
    
    # Use unified auth service
    auth_service = get_webapp_auth_service()
    parsed_data = auth_service.validate_init_data(raw_init_data)
    if not parsed_data:
        return False

    user_id = auth_service.get_user_id_from_init_data(parsed_data)
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

    protected_prefixes = ("/dj-admin/", "/dj-admin")

    def process_request(self, request):  # noqa: D401 - middleware hook
        path = request.path.rstrip("/") or "/"
        
        # Always allow standard Django admin login page
        if path in ("/dj-admin/login", "/dj-admin/login/"):
            return None
        
        if any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in self.protected_prefixes):
            # Allow GET/HEAD requests
            if request.method in {"GET", "HEAD"}:
                return None
            
            # Allow POST if user is authenticated as staff/superuser via Django session
            if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
                return None
            
            # Otherwise require Telegram admin validation for POST requests
            if not _is_telegram_admin(request):
                return _forbidden_response()
        return None


class TelegramAdminPermission(BasePermission):
    """DRF permission enforcing Telegram WebApp admin validation."""

    message = "Нет доступа"

    def has_permission(self, request, view):  # type: ignore[override]
        return _is_telegram_admin(request)
