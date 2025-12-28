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
    Returns True if task should abort without creating Meal.
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
    meal_id: int | None = None,
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

    Возвращаемое значение будет доступно через Celery result backend (polling ручка).
    """
    task_id = getattr(self.request, "id", None) or "unknown"
    rid = request_id or f"task-{str(task_id)[:8]}"

    # Импортируем модель внутри задачи, чтобы не тянуть ORM при старте воркера
    from apps.nutrition.models import Meal

    logger.info(
        "[AI] start task=%s meal_id=%s type=%s date=%s rid=%s user_id=%s",
        task_id,
        meal_id,
        meal_type,
        date,
        rid,
        user_id,
    )

    # 1) Validate mime_type (P0 Security/Integrity)
    # Hardened Validation: Verify image by magic bytes/Pillow
    if not mime_type or mime_type not in [
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/heic",
        "image/heif",
    ]:
        return {
            "error": "UNSUPPORTED_IMAGE_TYPE",
            "error_message": "Пожалуйста, загрузите изображение в формате JPEG, PNG или WEBP.",
            "items": [],
            "meal_id": None,
            "owner_id": user_id,  # P0-Ownership
        }

    # P0-D: Hardened validation using safe decode or magic bytes
    # _detect_mime_from_bytes (already imported) works by signature
    from apps.ai.serializers import _detect_mime_from_bytes

    detected = _detect_mime_from_bytes(image_bytes)

    # For HEIC we rely on client MIME as signatures are complex (ftyp)
    if not detected and mime_type not in ["image/heic", "image/heif"]:
        return {
            "error": "INVALID_IMAGE",
            "error_message": "Файл поврежден или не является изображением.",
            "items": [],
            "meal_id": None,
            "owner_id": user_id,  # P0-Ownership: Add explicit owner_id for robust fallback
        }

    # 2) Safely parse date
    import datetime

    parsed_date = None
    if isinstance(date, str):
        try:
            parsed_date = datetime.datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            logger.warning("[AI] Invalid date format: %s rid=%s", date, rid)
            return {
                "meal_id": None,
                "items": [],
                "totals": {},
                "error": "INVALID_DATE_FORMAT",
                "error_message": "Некорректный формат даты.",
                "owner_id": user_id,  # P0-Ownership
            }
    else:
        parsed_date = date or datetime.date.today()

    # P0 Security Check: restrict meal lookup to owner
    # If meal_id belongs to another user, we ignore it (meal will be None)
    meal = None
    if meal_id and user_id:
        meal = Meal.objects.filter(id=meal_id, user_id=user_id).first()
        if meal_id and not meal:
            logger.warning(
                "[AI] Meal not found or ownership mismatch: meal_id=%s user_id=%s", meal_id, user_id
            )

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

        # P1-3: Delete meal atomically if AI failed and meal exists
        if meal_id:
            try:
                from apps.nutrition.models import Meal

                meal = Meal.objects.filter(id=meal_id, user_id=user_id).first()
                if meal:
                    meal.delete()
                    logger.info(
                        "[AI] Deleted orphan meal_id=%s because AI proxy failed. rid=%s",
                        meal_id,
                        rid,
                    )
            except Exception:
                pass

        if isinstance(e, (AIProxyTimeoutError, AIProxyServerError)):
            # Временные проблемы — ретраим
            logger.warning(
                "[AI] retryable error task=%s meal_id=%s rid=%s err=%s",
                task_id,
                meal_id,
                rid,
                str(e),
            )
            # Re-delete meal on each retry just in case, but usually transaction helps
            raise self.retry(exc=e)

        # Любая неожиданная ошибка или валидация — не ретраим или ретраим ограниченно
        logger.exception("[AI] processing error task=%s meal_id=%s rid=%s", task_id, meal_id, rid)
        return {
            "meal_id": (meal.id if meal else meal_id),
            "items": [],
            "totals": {},
            "error": "AI_ERROR",
            "error_message": "Произошла ошибка при обработке фото. Попробуйте позже.",
            "owner_id": user_id,  # P0-Ownership
        }

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
        # P0-4: Delete meal if AI failed to prevent empty record in diary
        if meal:
            with transaction.atomic():
                meal.delete()

        # Возвращаем ошибку для polling — frontend увидит явный error
        return {
            "meal_id": meal_id,  # return original even if not owned
            "items": [],
            "totals": {},
            "meta": meta,
            "error": error_code,
            "error_message": error_message,
            "owner_id": user_id,  # P0-Ownership
        }

    # 2) Гарантируем валидные данные
    safe_items = _json_safe_items(items)

    # P0 Data Integrity: Delete meal if results are empty or error
    if not safe_items:
        if meal_id:
            try:
                from apps.nutrition.models import Meal

                meal = Meal.objects.filter(id=meal_id, user_id=user_id).first()
                if meal:
                    meal.delete()
                    logger.info(
                        "[AI] Deleted orphan meal_id=%s because result was empty/error. rid=%s",
                        meal_id,
                        rid,
                    )
            except Exception:
                pass

        return {
            "error": "EMPTY_RESULT",
            "error_message": "Не удалось распознать еду на фото.",
            "items": [],
            "meal_id": None,
            "owner_id": user_id,  # P0-Ownership
        }

    # P0-Cancel: Check if task was cancelled before creating Meal
    if _is_task_cancelled(task_id, user_id):
        logger.info(
            "[AI] Task cancelled before meal creation: task=%s user_id=%s rid=%s",
            task_id,
            user_id,
            rid,
        )
        return {
            "error": "CANCELLED",
            "error_message": "Отменено",
            "items": [],
            "meal_id": None,
            "owner_id": user_id,
        }

    # 3) Сохраняем в БД атомарно
    with transaction.atomic():
        if not meal:
            # Create new meal if not exists
            from django.contrib.auth import get_user_model
            from django.core.files.base import ContentFile

            User = get_user_model()
            user = User.objects.get(id=user_id)
            meal = Meal.objects.create(
                user=user,
                meal_type=meal_type,
                date=parsed_date,
            )
            # Attach photo
            import mimetypes

            if mime_type in ["image/heic", "image/heif"]:
                ext = "heic"
            else:
                ext = mimetypes.guess_extension(mime_type) or ".jpg"
                if ext.startswith("."):
                    ext = ext[1:]

            filename = f"ai_{rid}.{ext}" if rid else f"ai_{task_id}.{ext}"
            meal.photo.save(filename, ContentFile(image_bytes), save=False)
            meal.save()
            logger.info("[AI] created new meal_id=%s rid=%s", meal.id, rid)

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
        "meal_id": int(meal.id),
        "items": safe_items,
        "total_calories": float(totals.get("calories") or 0.0),
        "totals": {
            "calories": float(totals.get("calories") or 0.0),
            "protein": float(totals.get("protein") or 0.0),
            "fat": float(totals.get("fat") or 0.0),
            "carbohydrates": float(totals.get("carbohydrates") or 0.0),
        },
        "meta": meta,
        "owner_id": user_id,  # P0-Ownership
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
