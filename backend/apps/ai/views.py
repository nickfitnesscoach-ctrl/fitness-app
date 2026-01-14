"""
views.py — HTTP-эндпоинты AI распознавания.

Принцип:
- HTTP должен отвечать быстро.
- Долгая работа (AI) — только в Celery.

POST /api/v1/ai/recognize/
- Находит или создаёт Meal через get_or_create_draft_meal()
- Создаёт MealPhoto с status=PENDING
- Запускает Celery задачу и возвращает 202 + task_id + meal_id

Multi-Photo Meal Grouping:
- Если meal_id передан, фото прикрепляется к существующему meal
- Если нет, ищется draft meal в пределах 10-минутного окна
- Если не найден, создаётся новый draft meal

GET /api/v1/ai/task/<task_id>/
- polling статуса фоновой задачи
"""

from __future__ import annotations

import logging
from typing import Any, Dict
import uuid

from celery.result import AsyncResult
from django.conf import settings
from django.core.cache import cache
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import AIRecognizeRequestSerializer
from .tasks import recognize_food_async
from .throttles import (
    AIRecognitionPerDayThrottle,
    AIRecognitionPerMinuteThrottle,
    TaskStatusThrottle,
)

logger = logging.getLogger(__name__)


def _new_request_id() -> str:
    return uuid.uuid4().hex


class AIRecognitionView(APIView):
    """
    POST /api/v1/ai/recognize/
    Вход: {image, meal_type, date, user_comment, meal_id?}
    Выход: 202 {task_id, meal_id, status: 'processing'}

    Multi-Photo Meal Support:
    - meal_id передан → прикрепить фото к существующему meal
    - meal_id не передан → найти draft meal в 10-мин окне или создать новый
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    throttle_classes = [AIRecognitionPerMinuteThrottle, AIRecognitionPerDayThrottle]

    def post(self, request, *args, **kwargs):
        request_id = _new_request_id()

        s = AIRecognizeRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        normalized = s.validated_data["normalized_image"]
        meal_type = s.validated_data["meal_type"]
        meal_date = s.validated_data["date"]
        user_comment = s.validated_data.get("user_comment", "")
        client_meal_id = s.validated_data.get("meal_id")  # Optional: for multi-photo
        client_meal_photo_id = s.validated_data.get("meal_photo_id")  # Optional: for retry

        # P1-4: Проверяем лимит ДО создания Meal (избегаем orphan meals)
        # НО: при retry (meal_photo_id передан) не проверяем лимит — это повтор, не новый запрос
        from apps.billing.services import get_effective_plan_for_user
        from apps.billing.usage import DailyUsage

        if not client_meal_photo_id:  # Only check limit for NEW photos
            plan = get_effective_plan_for_user(request.user)
            limit = plan.daily_photo_limit  # None = безлимит

            if limit is not None:
                usage = DailyUsage.objects.get_today(request.user)
                if usage.photo_ai_requests >= limit:
                    logger.info(
                        "[AI] limit exceeded: user_id=%s used=%s limit=%s rid=%s",
                        request.user.id,
                        usage.photo_ai_requests,
                        limit,
                        request_id,
                    )
                    resp = Response(
                        {
                            "error": "DAILY_PHOTO_LIMIT_EXCEEDED",
                            "message": "Вы исчерпали дневной лимит фото",
                            "used": usage.photo_ai_requests,
                            "limit": limit,
                        },
                        status=status.HTTP_429_TOO_MANY_REQUESTS,
                    )
                    resp["X-Request-ID"] = request_id
                    return resp

        import mimetypes

        from django.core.files.base import ContentFile

        from apps.nutrition.models import MealPhoto
        from apps.nutrition.services import get_or_create_draft_meal

        mime_type = normalized.mime_type

        # RETRY MODE: Re-use existing MealPhoto instead of creating new
        if client_meal_photo_id:
            try:
                meal_photo = MealPhoto.objects.select_related("meal").get(
                    id=client_meal_photo_id,
                    meal__user=request.user,  # Security: verify ownership
                )
            except MealPhoto.DoesNotExist:
                resp = Response(
                    {"error": "PHOTO_NOT_FOUND", "message": "Фото не найдено"},
                    status=status.HTTP_404_NOT_FOUND,
                )
                resp["X-Request-ID"] = request_id
                return resp

            # Only allow retry on FAILED/CANCELLED photos
            if meal_photo.status not in ("FAILED", "CANCELLED"):
                resp = Response(
                    {
                        "error": "INVALID_STATUS",
                        "message": "Можно повторить только неудавшиеся фото",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
                resp["X-Request-ID"] = request_id
                return resp

            meal = meal_photo.meal

            # Reset photo status for retry
            meal_photo.status = "PENDING"
            meal_photo.error_message = None
            meal_photo.recognized_data = None
            meal_photo.save(update_fields=["status", "error_message", "recognized_data"])

            logger.info(
                "[AI] Retry MealPhoto id=%s for meal_id=%s user_id=%s rid=%s",
                meal_photo.id,
                meal.id,
                request.user.id,
                request_id,
            )
        else:
            # NEW PHOTO MODE: Find or create draft meal and new MealPhoto
            meal, created = get_or_create_draft_meal(
                user=request.user,
                meal_type=meal_type,
                meal_date=meal_date,
                meal_id=client_meal_id,
            )

            # Determine file extension
            if mime_type in ["image/heic", "image/heif"]:
                ext = "heic"
            else:
                ext = mimetypes.guess_extension(mime_type) or ".jpg"
                if ext.startswith("."):
                    ext = ext[1:]

            filename = f"ai_{request_id}.{ext}"

            meal_photo = MealPhoto.objects.create(
                meal=meal,
                status="PENDING",
            )
            # Save image file
            meal_photo.image.save(filename, ContentFile(normalized.bytes_data), save=True)

            logger.info(
                "[AI] Created MealPhoto id=%s for meal_id=%s user_id=%s rid=%s",
                meal_photo.id,
                meal.id,
                request.user.id,
                request_id,
            )

        # Update meal status to PROCESSING
        if meal.status == "DRAFT":
            meal.status = "PROCESSING"
            meal.save(update_fields=["status"])

        # 1) Async — основной режим (быстро и безопасно)
        if getattr(settings, "AI_ASYNC_ENABLED", True):
            task = recognize_food_async.delay(
                meal_id=meal.id,
                meal_photo_id=meal_photo.id,  # NEW: track which photo
                meal_type=meal_type,
                date=meal_date,
                image_bytes=normalized.bytes_data,
                mime_type=mime_type,
                user_comment=user_comment,
                request_id=request_id,
                user_id=request.user.id,
            )

            # P0 Security Check: link task to user in cache (24h TTL)
            cache.set(f"ai_task_owner:{task.id}", request.user.id, timeout=86400)
            # Store photo ID for immediate cancellation feedback
            cache.set(f"ai_task_photo:{task.id}", meal_photo.id, timeout=86400)

            # Return meal_id so frontend can group subsequent photos
            data = {
                "task_id": str(task.id),
                "meal_id": meal.id,
                "meal_photo_id": meal_photo.id,
                "status": "processing",
            }
            resp = Response(data, status=status.HTTP_202_ACCEPTED)
            resp["X-Request-ID"] = request_id
            return resp

        # 2) Sync — только для dev (не включать в проде)
        result = recognize_food_async.apply(
            kwargs=dict(
                meal_id=meal.id,
                meal_photo_id=meal_photo.id,
                meal_type=meal_type,
                date=meal_date,
                image_bytes=normalized.bytes_data,
                mime_type=mime_type,
                user_comment=user_comment,
                request_id=request_id,
                user_id=request.user.id,
            )
        ).get()

        resp = Response(result, status=status.HTTP_200_OK)
        resp["X-Request-ID"] = request_id
        return resp


class TaskStatusView(APIView):
    """
    GET /api/v1/ai/task/<task_id>/
    Опрос статуса Celery задачи.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [TaskStatusThrottle]

    def get(self, request: Request, task_id: str) -> Response:
        request_id = request.headers.get("X-Request-ID", "")

        # 1) SECURITY: Проверка владения задачей
        owner_id = cache.get(f"ai_task_owner:{task_id}")
        owner_verified = False

        if owner_id is not None:
            if int(owner_id) == request.user.id:
                owner_verified = True
        else:
            # P0-B: FALLBACK - Если кэш пуст, проверяем payload (даже если SUCCESS=error)
            res = AsyncResult(task_id)
            # Мы доверяем результату, ТОЛЬКО если в нём есть owner_id, совпадающий с request.user
            if res.ready():  # SUCCESS or FAILURE (but mainly SUCCESS carries payload)
                payload = res.result
                if isinstance(payload, dict):
                    # Вариант 1: owner_id в payload (самый надёжный transient fallback)
                    res_owner = payload.get("owner_id")
                    if res_owner and int(res_owner) == request.user.id:
                        # P0-Security: Double verification via DB if meal exists
                        meal_id = payload.get("meal_id")
                        if meal_id:
                            try:
                                from apps.nutrition.models import Meal

                                if Meal.objects.filter(
                                    id=meal_id, user_id=request.user.id
                                ).exists():
                                    cache.set(
                                        f"ai_task_owner:{task_id}", request.user.id, timeout=86400
                                    )
                                    owner_verified = True
                            except Exception:
                                pass
                        else:
                            # Trust owner_id for error/empty results (no DB record to verify)
                            cache.set(f"ai_task_owner:{task_id}", request.user.id, timeout=86400)
                            owner_verified = True

                    # Вариант 2 can be removed or kept as legacy fallback, but Variant 1 covers it better now.
                    # Keeping it simple as requested logic loop is closed by the block above for owner_id.

        if not owner_verified:
            logger.warning(
                "Unauthorized access attempt to AI task result: user_id=%s task_id=%s rid=%s",
                request.user.id,
                task_id,
                request_id,
            )
            return Response(
                {"error": "Task not found or access denied"}, status=status.HTTP_404_NOT_FOUND
            )

        # res is already defined above in fallback block or needs to be
        if "res" not in locals():
            res = AsyncResult(task_id)

        state = res.state

        # P0-API: Consistent Payload
        if state == "SUCCESS":
            payload: Dict[str, Any] = res.result or {}

            # Ensure items list exists for safe mapping on frontend
            payload.setdefault("items", [])
            payload.setdefault("totals", {})  # P0: Guarantee totals existence

            # P1: Hygiene - Remove internal owner_id before sending to client
            payload.pop("owner_id", None)

            # Check if logic-level error exists in payload
            if payload.get("error"):
                data = {
                    "task_id": task_id,
                    "status": "failed",
                    "state": state,
                    "error": payload["error"],
                    "result": payload,
                }
            else:
                data = {"task_id": task_id, "status": "success", "state": state, "result": payload}

            resp = Response(data, status=status.HTTP_200_OK)
            resp["X-Request-ID"] = request_id
            return resp

        if state == "FAILURE":
            # Клиенту — безопасно и кратко. В логи — подробнее.
            logger.warning("AI task failed: task_id=%s error=%r", task_id, res.result)
            data = {
                "task_id": task_id,
                "status": "failed",
                "state": state,
                "error": "Произошла ошибка при обработке. Попробуйте ещё раз.",
            }
            resp = Response(data, status=status.HTTP_200_OK)
            resp["X-Request-ID"] = request_id
            return resp

        data = {"task_id": task_id, "status": "processing", "state": state}
        resp = Response(data, status=status.HTTP_200_OK)
        resp["X-Request-ID"] = request_id
        return resp


class CancelTaskView(APIView):
    """
    POST /api/v1/ai/task/<task_id>/cancel/

    Marks a task as cancelled. The Celery task will check this flag
    before creating a Meal, preventing orphan diary entries.

    Fire-and-forget from frontend perspective - always returns 200.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, task_id: str) -> Response:
        request_id = request.headers.get("X-Request-ID", "")

        # Security: Verify task belongs to this user
        owner_id = cache.get(f"ai_task_owner:{task_id}")

        if owner_id is None:
            # Task doesn't exist or already expired - that's fine, just log
            logger.info(
                "[AI] Cancel request for unknown task: task_id=%s user_id=%s rid=%s",
                task_id,
                request.user.id,
                request_id,
            )
            return Response({"ok": True}, status=status.HTTP_200_OK)

        if int(owner_id) != request.user.id:
            # Security: Don't reveal task existence to non-owners
            logger.warning(
                "[AI] Unauthorized cancel attempt: task_id=%s user_id=%s owner_id=%s rid=%s",
                task_id,
                request.user.id,
                owner_id,
                request_id,
            )
            return Response({"ok": True}, status=status.HTTP_200_OK)

        # Set cancellation flag (24h TTL same as task ownership)
        cache.set(f"ai_task_cancelled:{task_id}", request.user.id, timeout=86400)

        # P0 Immediate Feedback: Update MealPhoto status and finalize
        meal_photo_id = cache.get(f"ai_task_photo:{task_id}")
        if meal_photo_id:
            from apps.nutrition.models import MealPhoto
            from apps.nutrition.services import finalize_meal_if_complete

            try:
                photo = MealPhoto.objects.get(id=meal_photo_id)
                if photo.status not in ("SUCCESS", "FAILED", "CANCELLED"):
                    photo.status = "CANCELLED"
                    photo.error_message = "Отменено пользователем"
                    photo.save(update_fields=["status", "error_message"])

                    # Finalize meal status
                    finalize_meal_if_complete(photo.meal)
                    logger.info("[AI] Mark MealPhoto %s as CANCELLED immediately", meal_photo_id)
            except Exception as e:
                logger.error(
                    "[AI] Failed to update MealPhoto %s on cancel: %s", meal_photo_id, str(e)
                )

        logger.info(
            "[AI] Task cancelled: task_id=%s user_id=%s rid=%s",
            task_id,
            request.user.id,
            request_id,
        )

        return Response({"ok": True}, status=status.HTTP_200_OK)
