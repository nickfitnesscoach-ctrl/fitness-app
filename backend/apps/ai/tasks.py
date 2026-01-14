"""
tasks.py — Celery задачи AI распознавания.

Multi-Photo Meal Architecture:
- View создаёт MealPhoto с status=PENDING
- Эта задача:
  1) Обновляет MealPhoto.status=PROCESSING
  2) Вызывает AI Proxy
  3) Создаёт FoodItem записи (добавляет, не перезаписывает)
  4) Сохраняет recognized_data в MealPhoto
  5) Обновляет MealPhoto.status=SUCCESS/FAILED
  6) Вызывает finalize_meal_if_complete()

Главные правила:
- НЕ удаляем Meal при ошибке одного фото (другие могут успеть)
- БЕЗ автоматических retry — пользователь нажмёт "Повторить" вручную
- Граммовка всегда >= 1 (иначе упадёт валидатор FoodItem)
- DecimalField сохраняем через Decimal(str(x))
- Никаких секретов в логах
"""

from __future__ import annotations

from decimal import Decimal
import logging
from typing import Any, Dict, List

from celery import shared_task
from django.db import transaction

from apps.ai_proxy import (
    AIProxyServerError,
    AIProxyService,
    AIProxyTimeoutError,
)
from apps.common.nutrition_utils import clamp_grams

logger = logging.getLogger(__name__)


def _to_decimal(value: Any, default: str = "0") -> Decimal:
    """Безопасное преобразование к Decimal для DecimalField."""
    try:
        if value is None:
            return Decimal(default)
        return Decimal(str(value))
    except Exception:
        return Decimal(default)


def _is_task_cancelled(task_id: str, user_id: int | None) -> bool:
    """
    Check if task was cancelled by user via CancelTaskView.
    Returns True if task should abort without processing.
    """
    from django.core.cache import cache

    cancelled_by = cache.get(f"ai_task_cancelled:{task_id}")
    if cancelled_by is not None:
        # Verify it was cancelled by the same user (security)
        if user_id is None or int(cancelled_by) == user_id:
            return True
    return False


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


def _update_meal_photo_failed(meal_photo_id: int | None, error_code: str, error_message: str):
    """Update MealPhoto to FAILED status and trigger finalization check."""
    if not meal_photo_id:
        # Legacy/bot call without pre-created photo - nothing to update
        return

    from apps.nutrition.models import MealPhoto
    from apps.nutrition.services import finalize_meal_if_complete

    try:
        with transaction.atomic():
            photo = MealPhoto.objects.select_for_update().get(id=meal_photo_id)
            # Only update if not already in terminal state
            if photo.status not in ("SUCCESS", "FAILED", "CANCELLED"):
                photo.status = "CANCELLED" if error_code == "CANCELLED" else "FAILED"
                photo.error_code = error_code  # P1.5: Store structured code
                photo.error_message = error_message
                photo.recognized_data = {"error": error_code, "error_message": error_message}
                photo.save(
                    update_fields=["status", "error_code", "error_message", "recognized_data"]
                )

                # P1.5: Structured logging for observability (grep-friendly)
                logger.warning(
                    "[AI:FAILED] photo_id=%s user_id=%s error_code=%s meal_id=%s",
                    meal_photo_id,
                    photo.meal.user_id if photo.meal else None,
                    error_code,
                    photo.meal_id,
                )

            # Always check if meal should be finalized
            finalize_meal_if_complete(photo.meal)
    except MealPhoto.DoesNotExist:
        logger.warning("[AI] MealPhoto %s not found for status update", meal_photo_id)
    except Exception as e:
        logger.error("[AI] Failed to update MealPhoto %s: %s", meal_photo_id, str(e))


@shared_task(bind=True)
def recognize_food_async(
    self,
    *,
    meal_id: int,  # Required: meal already created by view
    meal_photo_id: int,  # Required: MealPhoto already created by view
    meal_type: str = "SNACK",
    date: str | None = None,
    image_bytes: bytes,
    mime_type: str,
    user_comment: str = "",
    request_id: str = "",
    user_id: int | None = None,
) -> Dict[str, Any]:
    """
    Основная задача: распознать еду по фото и сохранить items в БД.

    Multi-Photo Architecture:
    - Meal и MealPhoto уже созданы в view
    - Обновляем MealPhoto.status по ходу работы
    - Добавляем FoodItem к Meal (не перезаписываем)
    - При ошибке одного фото — Meal сохраняется (другие могут успеть)

    Возвращаемое значение будет доступно через Celery result backend (polling ручка).
    """
    task_id = getattr(self.request, "id", None) or "unknown"
    rid = request_id or f"task-{str(task_id)[:8]}"

    # Импортируем модели внутри задачи
    from apps.nutrition.models import Meal, MealPhoto
    from apps.nutrition.services import finalize_meal_if_complete

    logger.info(
        "[AI] start task=%s meal_id=%s photo_id=%s type=%s date=%s rid=%s user_id=%s",
        task_id,
        meal_id,
        meal_photo_id,
        meal_type,
        date,
        rid,
        user_id,
    )

    # 1. Prepare photo (multi-photo architecture: already created by view)
    meal_photo = None
    if meal_photo_id:
        try:
            meal_photo = MealPhoto.objects.select_related("meal").get(id=meal_photo_id)
        except MealPhoto.DoesNotExist:
            logger.error("[AI] MealPhoto %s not found, aborting task", meal_photo_id)
            return {
                "error": "PHOTO_NOT_FOUND",
                "error_message": "Фото не найдено.",
                "items": [],
                "meal_id": meal_id,
                "meal_photo_id": meal_photo_id,
                "owner_id": user_id,
            }

        # Sync check: ensure photo belongs to meal
        if meal_id and meal_photo.meal_id != meal_id:
            logger.error("[AI] Photo %s doesn't belong to meal %s", meal_photo_id, meal_id)
            return {
                "error": "OWNERSHIP_MISMATCH",
                "error_message": "Фото не принадлежит указанному приёму пищи.",
                "items": [],
                "meal_id": meal_id,
                "meal_photo_id": meal_photo_id,
                "owner_id": user_id,
            }

        # Update MealPhoto to PROCESSING
        with transaction.atomic():
            meal_photo.status = "PROCESSING"
            meal_photo.save(update_fields=["status"])
    else:
        logger.info("[AI] No meal_photo_id provided, continuing (bot/legacy call)")

    # 1) Validate mime_type (P0 Security/Integrity)
    if not mime_type or mime_type not in [
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/heic",
        "image/heif",
    ]:
        _update_meal_photo_failed(
            meal_photo_id,
            "UNSUPPORTED_IMAGE_TYPE",
            "Пожалуйста, загрузите изображение в формате JPEG, PNG или WEBP.",
        )
        return {
            "error": "UNSUPPORTED_IMAGE_TYPE",
            "error_message": "Пожалуйста, загрузите изображение в формате JPEG, PNG или WEBP.",
            "items": [],
            "meal_id": meal_id,
            "meal_photo_id": meal_photo_id,
            "owner_id": user_id,
        }

    # P0-D: Hardened validation using magic bytes
    from apps.ai.serializers import _detect_mime_from_bytes

    detected = _detect_mime_from_bytes(image_bytes)

    # For HEIC we rely on client MIME as signatures are complex (ftyp)
    if not detected and mime_type not in ["image/heic", "image/heif"]:
        _update_meal_photo_failed(
            meal_photo_id, "INVALID_IMAGE", "Файл поврежден или не является изображением."
        )
        return {
            "error": "INVALID_IMAGE",
            "error_message": "Файл поврежден или не является изображением.",
            "items": [],
            "meal_id": meal_id,
            "meal_photo_id": meal_photo_id,
            "owner_id": user_id,
        }

    # 2) Safely parse date
    import datetime

    parsed_date = None
    if isinstance(date, str):
        try:
            parsed_date = datetime.datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            logger.warning("[AI] Invalid date format: %s rid=%s", date, rid)
            _update_meal_photo_failed(
                meal_photo_id, "INVALID_DATE_FORMAT", "Некорректный формат даты."
            )
            return {
                "meal_id": meal_id,
                "meal_photo_id": meal_photo_id,
                "items": [],
                "totals": {},
                "error": "INVALID_DATE_FORMAT",
                "error_message": "Некорректный формат даты.",
                "owner_id": user_id,
            }
    else:
        parsed_date = date or datetime.date.today()

    # P0 Security Check: Verify meal ownership
    meal = Meal.objects.filter(id=meal_id, user_id=user_id).first()
    if not meal:
        logger.warning(
            "[AI] Meal not found or ownership mismatch: meal_id=%s user_id=%s", meal_id, user_id
        )
        _update_meal_photo_failed(meal_photo_id, "MEAL_NOT_FOUND", "Приём пищи не найден.")
        return {
            "error": "MEAL_NOT_FOUND",
            "error_message": "Приём пищи не найден.",
            "items": [],
            "meal_id": meal_id,
            "meal_photo_id": meal_photo_id,
            "owner_id": user_id,
        }

    # P0-Cancel: Check if task was cancelled
    if _is_task_cancelled(task_id, user_id):
        logger.info(
            "[AI] Task cancelled: task=%s user_id=%s rid=%s",
            task_id,
            user_id,
            rid,
        )
        _update_meal_photo_failed(meal_photo_id, "CANCELLED", "Отменено")
        return {
            "error": "CANCELLED",
            "error_message": "Отменено",
            "items": [],
            "meal_id": meal_id,
            "meal_photo_id": meal_photo_id,
            "owner_id": user_id,
        }

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
    except Exception as e:
        logger.error("[AI] Proxy error: %r rid=%s", e, rid)

        # Определяем сообщение в зависимости от типа ошибки
        if isinstance(e, AIProxyTimeoutError):
            error_code = "AI_TIMEOUT"
            error_message = "Сервер не ответил вовремя. Попробуйте ещё раз."
        elif isinstance(e, AIProxyServerError):
            error_code = "AI_SERVER_ERROR"
            error_message = "Сервер временно недоступен. Попробуйте ещё раз."
        else:
            error_code = "AI_ERROR"
            error_message = "Произошла ошибка при обработке фото. Попробуйте позже."

        # Сразу помечаем фото как FAILED (без retry — пользователь нажмёт "Повторить" сам)
        _update_meal_photo_failed(meal_photo_id, error_code, error_message)
        return {
            "meal_id": meal_id,
            "meal_photo_id": meal_photo_id,
            "items": [],
            "totals": {},
            "error": error_code,
            "error_message": error_message,
            "owner_id": user_id,
        }

    items = result.items
    totals = result.totals
    meta = result.meta

    # P0-2: Обрабатываем controlled error
    if meta.get("is_error"):
        error_code = meta.get("error_code", "UNKNOWN")
        error_message = meta.get(
            "error_message", "Не удалось распознать еду на фото. Попробуйте ещё раз."
        )
        logger.warning(
            "[AI] controlled error task=%s meal_id=%s photo_id=%s rid=%s code=%s",
            task_id,
            meal_id,
            meal_photo_id,
            rid,
            error_code,
        )
        _update_meal_photo_failed(meal_photo_id, error_code, error_message)
        return {
            "meal_id": meal_id,
            "meal_photo_id": meal_photo_id,
            "items": [],
            "totals": {},
            "meta": meta,
            "error": error_code,
            "error_message": error_message,
            "owner_id": user_id,
        }

    # 2) Гарантируем валидные данные
    safe_items = _json_safe_items(items)

    # P0 Data Integrity: Handle empty results
    if not safe_items:
        _update_meal_photo_failed(
            meal_photo_id, "EMPTY_RESULT", "Не удалось распознать еду на фото."
        )
        return {
            "error": "EMPTY_RESULT",
            "error_message": "Не удалось распознать еду на фото.",
            "items": [],
            "meal_id": meal_id,
            "meal_photo_id": meal_photo_id,
            "owner_id": user_id,
        }

    # 3) Сохраняем в БД атомарно
    with transaction.atomic():
        # Reload meal and photo with lock
        meal = Meal.objects.select_for_update().get(id=meal_id)
        meal_photo = MealPhoto.objects.select_for_update().get(id=meal_photo_id)

        # Add FoodItems (APPEND, not replace — multi-photo mode)
        for it in safe_items:
            meal.items.create(
                name=it["name"],
                grams=it["amount_grams"],
                calories=_to_decimal(it["calories"], "0"),
                protein=_to_decimal(it["protein"], "0"),
                fat=_to_decimal(it["fat"], "0"),
                carbohydrates=_to_decimal(it["carbohydrates"], "0"),
            )

        # Update MealPhoto with success (if exists)
        if meal_photo_id:
            meal_photo = MealPhoto.objects.select_for_update().get(id=meal_photo_id)
            meal_photo.status = "SUCCESS"
            meal_photo.recognized_data = {
                "items": safe_items,
                "totals": {
                    "calories": float(totals.get("calories") or 0.0),
                    "protein": float(totals.get("protein") or 0.0),
                    "fat": float(totals.get("fat") or 0.0),
                    "carbohydrates": float(totals.get("carbohydrates") or 0.0),
                },
                "meta": meta,
            }
            meal_photo.save(update_fields=["status", "recognized_data"])
            logger.info(
                "[AI] MealPhoto %s updated to SUCCESS with %s items", meal_photo_id, len(safe_items)
            )
        else:
            logger.info("[AI] Success for meal_id=%s (no photo to update)", meal.id)

    # Check if meal should be finalized
    finalize_meal_if_complete(meal)

    # 4) P0-1: Инкрементируем usage ТОЛЬКО после успешного сохранения
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
        "meal_id": int(meal.id),
        "meal_photo_id": int(meal_photo_id) if meal_photo_id else None,
        "items": safe_items,
        "total_calories": float(totals.get("calories") or 0.0),
        "totals": {
            "calories": float(totals.get("calories") or 0.0),
            "protein": float(totals.get("protein") or 0.0),
            "fat": float(totals.get("fat") or 0.0),
            "carbohydrates": float(totals.get("carbohydrates") or 0.0),
        },
        "meta": meta,
        "owner_id": user_id,
    }

    logger.info(
        "[AI] done task=%s meal_id=%s photo_id=%s rid=%s items=%s kcal=%.1f",
        task_id,
        meal_id,
        meal_photo_id,
        rid,
        len(safe_items),
        float(totals.get("calories") or 0.0),
    )
    return response
