"""
client.py — HTTP клиент для внутреннего сервиса AI Proxy.

Простыми словами:
- AI Proxy — отдельный микросервис, который распознаёт еду по фото.
- Этот файл отвечает только за:
  1) собрать HTTP запрос (multipart/form-data)
  2) добавить секрет (X-API-Key)
  3) поставить безопасные таймауты
  4) разобрать ответ (JSON)
  5) превратить HTTP ошибки в понятные Python-исключения

ВАЖНО (P0):
- НЕЛЬЗЯ делать огромные таймауты (типа 130 секунд) в sync HTTP.
- Мы вызываем AI Proxy из Celery (фон), поэтому таймаут 40 сек суммарно — ок.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Dict, Optional

from django.conf import settings
import requests

from .exceptions import (
    AIProxyAuthenticationError,
    AIProxyServerError,
    AIProxyTimeoutError,
    AIProxyValidationError,
)
from .utils import join_url, safe_json_loads

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Конфигурация клиента
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AIProxyConfig:
    """
    Настройки подключения к AI Proxy.

    Простыми словами:
    - url: куда отправляем запрос
    - secret: ключ доступа (передаём через X-API-Key)
    """

    url: str
    secret: str

    @staticmethod
    def from_django_settings() -> "AIProxyConfig":
        # Берём из config/settings/*.py (у тебя это уже есть в base.py)
        url = getattr(settings, "AI_PROXY_URL", "") or ""
        secret = getattr(settings, "AI_PROXY_SECRET", "") or ""

        if not url:
            raise AIProxyServerError("AI_PROXY_URL не задан в настройках Django")
        if not secret:
            raise AIProxyAuthenticationError("AI_PROXY_SECRET не задан в настройках Django")

        return AIProxyConfig(url=url, secret=secret)


# ---------------------------------------------------------------------------
# Клиент
# ---------------------------------------------------------------------------


class AIProxyClient:
    """
    Низкоуровневый HTTP клиент.

    Использовать напрямую можно, но обычно вызывается через:
    AIProxyService -> AIProxyClient
    """

    # Реальный endpoint AI Proxy (из твоего FastAPI кода)
    _RECOGNIZE_PATH = "/api/v1/ai/recognize-food"

    def __init__(
        self,
        config: Optional[AIProxyConfig] = None,
        *,
        connect_timeout_s: float = 5.0,
        read_timeout_s: float = 35.0,
    ) -> None:
        self._config = config or AIProxyConfig.from_django_settings()
        self._timeout = (connect_timeout_s, read_timeout_s)

        # requests.Session — чуть быстрее и проще (keep-alive)
        self._session = requests.Session()

        # Секрет кладём только в заголовок. В логи никогда не выводим.
        self._default_headers = {
            "Accept": "application/json",
            "X-API-Key": self._config.secret,
        }

    def _build_url(self, path: str) -> str:
        return join_url(self._config.url, path)

    def recognize_food(
        self,
        *,
        image_bytes: bytes,
        content_type: str,
        user_comment: str = "",
        locale: str = "ru",
        request_id: str = "",
    ) -> Dict[str, Any]:
        """
        Отправляет фото в AI Proxy и возвращает сырой JSON dict.

        Вход:
        - image_bytes: байты изображения
        - content_type: "image/jpeg" / "image/png"
        - user_comment: опционально
        - locale: "ru"/"en"
        - request_id: пробрасываем для трассировки (X-Request-ID)
        """
        if not image_bytes:
            raise AIProxyValidationError("Пустое изображение (image_bytes пустой)")

        url = self._build_url(self._RECOGNIZE_PATH)

        headers = dict(self._default_headers)
        if request_id:
            # AI Proxy middleware читает X-Request-ID и добавляет его в ответ
            headers["X-Request-ID"] = request_id

        # multipart/form-data:
        # image — файл, user_comment/locale — поля формы
        files = {
            "image": ("image", image_bytes, content_type),
        }
        data = {
            "locale": locale or "ru",
        }
        if user_comment:
            data["user_comment"] = user_comment

        try:
            resp = self._session.post(
                url,
                headers=headers,
                files=files,
                data=data,
                timeout=self._timeout,
            )
        except requests.Timeout as e:
            # Таймаут — временная проблема (ретраим в Celery)
            raise AIProxyTimeoutError(f"AI Proxy timeout: {e}") from e
        except requests.RequestException as e:
            # Сеть/соединение — временная проблема (ретраим)
            raise AIProxyServerError(f"AI Proxy network error: {e}") from e

        # Пытаемся разобрать JSON (AI Proxy возвращает JSON)
        body_text = resp.text or ""
        payload, preview = safe_json_loads(body_text)

        # ------------------------------------------------------------
        # Карта ошибок (важно для retry policy)
        # ------------------------------------------------------------
        status = resp.status_code

        # 401/403 — секрет неверный/нет доступа (ретраи бессмысленны)
        if status in (401, 403):
            detail = payload.get("detail") if isinstance(payload, dict) else None
            raise AIProxyAuthenticationError(
                f"AI Proxy auth error {status}: {detail or preview or 'unauthorized'}"
            )

        # 400/413/422/429 — ошибки запроса (ретраи бессмысленны)
        if status in (400, 413, 422, 429):
            detail = payload.get("detail") if isinstance(payload, dict) else None
            raise AIProxyValidationError(
                f"AI Proxy validation error {status}: {detail or preview or 'bad request'}"
            )

        # 5xx — проблема сервера AI Proxy (ретраим)
        if 500 <= status <= 599:
            detail = payload.get("detail") if isinstance(payload, dict) else None
            raise AIProxyServerError(
                f"AI Proxy server error {status}: {detail or preview or 'server error'}"
            )

        # Любой другой неожиданный статус — считаем серверной проблемой (лучше ретраить ограниченно)
        if status < 200 or status >= 300:
            raise AIProxyServerError(
                f"AI Proxy unexpected status {status}: {preview or body_text[:200]}"
            )

        # Успех: payload должен быть dict
        if not payload:
            raise AIProxyServerError("AI Proxy returned empty or non-object JSON response")

        return payload
