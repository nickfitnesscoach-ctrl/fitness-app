"""
apps.ai_proxy — модуль для общения с AI Proxy сервисом.

Простыми словами:
- AI Proxy — отдельный сервис, который распознаёт еду по фото
- backend вызывает его только из Celery задач (долго ждать нельзя)
"""

from __future__ import annotations

from .exceptions import (
    AIProxyAuthenticationError,
    AIProxyError,
    AIProxyServerError,
    AIProxyTimeoutError,
    AIProxyValidationError,
)
from .service import AIProxyService, RecognizeFoodResult

__all__ = [
    "AIProxyService",
    "RecognizeFoodResult",
    "AIProxyError",
    "AIProxyValidationError",
    "AIProxyAuthenticationError",
    "AIProxyTimeoutError",
    "AIProxyServerError",
]
