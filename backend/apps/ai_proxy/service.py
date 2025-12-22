"""
service.py — высокоуровневый сервис для распознавания еды через AI Proxy.

Простыми словами:
- tasks.py не должен знать детали HTTP и форматы ответа разных моделей
- tasks.py вызывает 1 метод сервиса и получает стабильный результат:
  {
    "items": [...],
    "totals": {...},
    "meta": {...}
  }

Это упрощает поддержку:
- меняется AI Proxy формат → правим только adapter.py/service.py
- tasks.py остаётся стабильным
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .adapter import normalize_proxy_response
from .client import AIProxyClient


@dataclass(frozen=True)
class RecognizeFoodResult:
    """
    Результат распознавания, уже нормализованный и готовый для сохранения в БД.

    items  — список блюд/продуктов с КБЖУ и граммовкой
    totals — суммарные КБЖУ
    meta   — служебная инфа (request_id, модель и т.д.)
    """

    items: list[dict[str, Any]]
    totals: dict[str, float]
    meta: dict[str, Any]


class AIProxyService:
    """
    Сервис-обёртка над AIProxyClient.
    """

    def __init__(self, client: Optional[AIProxyClient] = None) -> None:
        self._client = client or AIProxyClient()

    def recognize_food(
        self,
        *,
        image_bytes: bytes,
        content_type: str,
        user_comment: str = "",
        locale: str = "ru",
        request_id: str = "",
    ) -> RecognizeFoodResult:
        """
        Распознаёт еду по фото.

        Возвращает нормализованный результат:
        - items (с гарантией grams>=1 и типами float/int)
        - totals
        - meta
        """
        raw: dict[str, Any] = self._client.recognize_food(
            image_bytes=image_bytes,
            content_type=content_type,
            user_comment=user_comment,
            locale=locale,
            request_id=request_id,
        )

        # normalize_proxy_response теперь включает totals
        normalized = normalize_proxy_response(raw, request_id=request_id)
        items = normalized.get("items") or []
        totals = normalized.get("totals") or {}
        meta = normalized.get("meta") or {}

        return RecognizeFoodResult(items=items, totals=totals, meta=meta)
