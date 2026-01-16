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

from dataclasses import dataclass
import logging
from typing import Any, Optional

from .adapter import normalize_proxy_response
from .client import AIProxyClient
from .utils import normalize_image

logger = logging.getLogger(__name__)


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

        HARD SLA:
        - Нормализация выполняется ровно 1 раз (до base64, до ретраев)
        - В Vision уходит ТОЛЬКО: JPEG, <=1024px longest side
        """
        # 1. Image Normalization (exactly ONCE per request)
        try:
            norm_bytes, norm_content_type, norm_metrics = normalize_image(
                image_bytes=image_bytes,
                content_type=content_type,
            )

            # Log metrics (internal debugging only, NO bytes/base64)
            logger.info(
                "Image normalization: request_id=%s, action=%s, reason=%s, "
                "content_type_in=%s, content_type_out=%s, "
                "original=%sB (%s, longest=%dpx), normalized=%sB (%s, longest=%dpx), "
                "processing_ms=%d",
                request_id,
                norm_metrics.get("action", "unknown"),
                norm_metrics.get("reason", "unknown"),
                norm_metrics.get("content_type_in", "unknown"),
                norm_metrics.get("content_type_out", "unknown"),
                norm_metrics.get("original_size_bytes", 0),
                norm_metrics.get("original_px", "0x0"),
                norm_metrics.get("original_longest_side", 0),
                norm_metrics.get("normalized_size_bytes", 0),
                norm_metrics.get("normalized_px", "0x0"),
                norm_metrics.get("normalized_longest_side", 0),
                norm_metrics.get("processing_ms", 0),
            )

            # 2. Check action: if reject → controlled error, NO client call
            if norm_metrics.get("action") == "reject":
                reason = norm_metrics.get("reason", "unknown")

                # Import Error Contract для нормализации ошибок
                from apps.ai.error_contract import AIErrorRegistry

                # Unified error_code mapping by reason only
                if reason == "unsupported_format":
                    error_def = AIErrorRegistry.UNSUPPORTED_IMAGE_FORMAT
                else:
                    # decode_failed, save_failed, too_slow, unknown → IMAGE_DECODE_FAILED
                    error_def = AIErrorRegistry.IMAGE_DECODE_FAILED

                return RecognizeFoodResult(
                    items=[],
                    totals={},
                    meta={
                        "request_id": request_id,
                        "is_error": True,
                        **error_def.to_dict(trace_id=request_id),
                    },
                )

            # Use normalized data for the request
            image_bytes = norm_bytes
            content_type = norm_content_type

        except Exception as e:
            # Unexpected error during normalization → controlled error
            logger.exception(
                "Unexpected normalization error: request_id=%s, error=%s", request_id, e
            )

            from apps.ai.error_contract import AIErrorRegistry
            error_def = AIErrorRegistry.IMAGE_DECODE_FAILED

            return RecognizeFoodResult(
                items=[],
                totals={},
                meta={
                    "request_id": request_id,
                    "is_error": True,
                    **error_def.to_dict(trace_id=request_id, debug_details={"exception": str(e)}),
                },
            )

        # 3. Final assert (safety net for future regressions)
        # If we reach here with non-JPEG or large image → reject
        normalized_longest = norm_metrics.get("normalized_longest_side", 0)
        if content_type != "image/jpeg" or normalized_longest > 1024:
            logger.error(
                "FINAL ASSERT FAILED: request_id=%s, content_type=%s, longest=%d",
                request_id,
                content_type,
                normalized_longest,
            )

            from apps.ai.error_contract import AIErrorRegistry
            error_def = AIErrorRegistry.INVALID_IMAGE

            return RecognizeFoodResult(
                items=[],
                totals={},
                meta={
                    "request_id": request_id,
                    "is_error": True,
                    **error_def.to_dict(
                        trace_id=request_id,
                        debug_details={
                            "content_type": content_type,
                            "longest_side": normalized_longest,
                        },
                    ),
                },
            )

        # 4. API Request (uses same normalized bytes for any retries)
        # client.recognize_food() теперь возвращает AIProxyResult
        from .client import AIProxyResult

        result: AIProxyResult = self._client.recognize_food(
            image_bytes=image_bytes,
            content_type=content_type,
            user_comment=user_comment,
            locale=locale,
            request_id=request_id,
        )

        # Шаг 5: Обрабатываем AIProxyResult
        if not result.ok:
            # AI Proxy вернул structured error (UNSUPPORTED_CONTENT, EMPTY_RESULT, etc.)
            # result.payload уже содержит Error Contract
            # Возвращаем RecognizeFoodResult с is_error=True
            return RecognizeFoodResult(
                items=[],
                totals={},
                meta={
                    "request_id": request_id,
                    "is_error": True,
                    **result.payload,  # Содержит error_code, user_title, user_message, etc.
                },
            )

        # Шаг 6: Успех — нормализуем payload
        # normalize_proxy_response теперь включает totals
        normalized = normalize_proxy_response(result.payload, request_id=request_id)
        items = normalized.get("items") or []
        totals = normalized.get("totals") or {}
        meta = normalized.get("meta") or {}

        return RecognizeFoodResult(items=items, totals=totals, meta=meta)
