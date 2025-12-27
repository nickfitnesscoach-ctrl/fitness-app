"""
tasks.py — Celery задачи AI распознавания.

Простыми словами:
- HTTP ручка отвечает быстро (202) и отдаёт task_id
- эта задача в фоне:
  1) вызывает AI Proxy
  2) нормализует ответ
  3) сохраняет в FoodItem (meal.items)
  4) возвращает JSON-safe результат

Главные правила:
- ретраи только на timeout/5xx (временные проблемы)
- граммовка всегда >= 1 (иначе упадёт валидатор FoodItem)
- DecimalField сохраняем через Decimal(str(x))
- никаких секретов в логах
"""

from __future__ import annotations

from decimal import Decimal
import logging
from typing import Any, Dict, List

from celery import shared_task
from django.db import transaction

from apps.ai_proxy import (
    AIProxyAuthenticationError,
    AIProxyServerError,
    AIProxyService,
    AIProxyTimeoutError,
    AIProxyValidationError,
)

logger = logging.getLogger(__name__)

# P2-2: Используем общую функцию из common module
from apps.common.nutrition_utils import clamp_grams


def _to_decimal(value: Any, default: str = "0") -> Decimal:
    """Безопасное преобразование к Decimal для DecimalField."""
    try:
        if value is None:
            return Decimal(default)
        return Decimal(str(value))
    except Exception:
        return Decimal(default)


def _json_safe_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Делаем items гарантированно JSON-safe:
    - числа → float/int
    - строки → str
    """
    safe: List[Dict[str, Any]] = []
    for it in items:
        safe.append(
            {
                "name": str(it.get("name") or "Unknown"),
                "amount_grams": clamp_grams(it.get("grams")),  # API Contract field name
                "calories": float(it.get("calories") or 0.0),
                "protein": float(it.get("protein") or 0.0),
                "fat": float(it.get("fat") or 0.0),
                "carbohydrates": float(it.get("carbohydrates") or 0.0),
                # confidence может быть None — это ок для JSON
                "confidence": (
                    float(it["confidence"]) if it.get("confidence") is not None else None
                ),
            }
        )
    return safe


@shared_task(
    bind=True,
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
)
def recognize_food_async(
    self,
    *,
    meal_id: int,
    image_bytes: bytes,
    mime_type: str,
    user_comment: str = "",
    request_id: str = "",
    user_id: int | None = None,
) -> Dict[str, Any]:
    """
    Основная задача: распознать еду по фото и сохранить items в БД.

    Возвращаемое значение будет доступно через Celery result backend (polling ручка).
    """
    task_id = getattr(self.request, "id", None) or "unknown"
    rid = request_id or f"task-{str(task_id)[:8]}"

    # Импортируем модель внутри задачи, чтобы не тянуть ORM при старте воркера
    from apps.nutrition.models import Meal

    logger.info("[AI] start task=%s meal_id=%s rid=%s user_id=%s", task_id, meal_id, rid, user_id)

    meal = Meal.objects.get(id=meal_id)

    service = AIProxyService()

    # 1) Вызов AI Proxy (политика ошибок/ретраев)
    try:
        result = service.recognize_food(
            image_bytes=image_bytes,
            content_type=mime_type,
            user_comment=user_comment or "",
            locale="ru",
            request_id=rid,
        )
    except AIProxyValidationError as e:
        # Валидация не лечится ретраем
        logger.warning(
            "[AI] validation error task=%s meal_id=%s rid=%s err=%s", task_id, meal_id, rid, str(e)
        )
        raise
    except AIProxyAuthenticationError as e:
        # Неверный секрет — ретраи бессмысленны
        logger.error(
            "[AI] auth error task=%s meal_id=%s rid=%s err=%s", task_id, meal_id, rid, str(e)
        )
        raise
    except (AIProxyTimeoutError, AIProxyServerError) as e:
        # Временные проблемы — ретраим
        logger.warning(
            "[AI] retryable error task=%s meal_id=%s rid=%s err=%s", task_id, meal_id, rid, str(e)
        )
        raise self.retry(exc=e)
    except Exception as e:
        # Любая неожиданная ошибка — пробуем ретрай (ограниченно)
        logger.exception("[AI] unexpected error task=%s meal_id=%s rid=%s", task_id, meal_id, rid)
        raise self.retry(exc=e)

    items = result.items
    totals = result.totals
    meta = result.meta

    # P0-2: Обрабатываем controlled error — НЕ сохраняем в БД, НЕ списываем usage
    if meta.get("is_error"):
        error_code = meta.get("error_code", "UNKNOWN")
        error_message = meta.get("error_message", "AI processing failed")
        logger.warning(
            "[AI] controlled error task=%s meal_id=%s rid=%s code=%s",
            task_id,
            meal_id,
            rid,
            error_code,
        )
        # Возвращаем ошибку для polling — frontend увидит явный error
        return {
            "meal_id": int(meal_id),
            "items": [],
            "totals": {},
            "meta": meta,
            "error": error_code,
            "error_message": error_message,
        }

    # 2) Гарантируем валидные данные
    safe_items = _json_safe_items(items)

    # 3) Сохраняем в БД атомарно
    with transaction.atomic():
        # Если AI пересчитали — перезаписываем
        meal.items.all().delete()

        for it in safe_items:
            meal.items.create(
                name=it["name"],
                grams=it["amount_grams"],  # P1-3: use amount_grams from _json_safe_items
                calories=_to_decimal(it["calories"], "0"),
                protein=_to_decimal(it["protein"], "0"),
                fat=_to_decimal(it["fat"], "0"),
                carbohydrates=_to_decimal(it["carbohydrates"], "0"),
            )

    # 4) P0-1: Инкрементируем usage ТОЛЬКО после успешного сохранения
    # Это гарантирует, что лимит списывается только при реальном успехе AI
    if user_id:
        try:
            from django.contrib.auth import get_user_model

            from apps.billing.usage import DailyUsage

            User = get_user_model()
            user = User.objects.get(id=user_id)
            DailyUsage.objects.increment_photo_ai_requests(user)
            logger.info("[AI] usage incremented user_id=%s task=%s", user_id, task_id)
        except User.DoesNotExist:
            logger.warning(
                "[AI] user not found for usage increment: user_id=%s task=%s", user_id, task_id
            )
        except Exception as usage_err:
            # Ошибка учёта usage не должна ломать успешный результат
            logger.error("[AI] usage increment failed: user_id=%s err=%s", user_id, str(usage_err))

    response: Dict[str, Any] = {
        "meal_id": int(meal_id),
        "items": safe_items,
        "total_calories": float(totals.get("calories") or 0.0),
        "totals": {
            "calories": float(totals.get("calories") or 0.0),
            "protein": float(totals.get("protein") or 0.0),
            "fat": float(totals.get("fat") or 0.0),
            "carbohydrates": float(totals.get("carbohydrates") or 0.0),
        },
        "meta": meta,
    }

    logger.info(
        "[AI] done task=%s meal_id=%s rid=%s items=%s kcal=%.1f",
        task_id,
        meal_id,
        rid,
        len(safe_items),
        float(totals.get("calories") or 0.0),
    )
    return response
