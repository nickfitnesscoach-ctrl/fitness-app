"""
views.py — HTTP-эндпоинты AI распознавания.

Принцип:
- HTTP должен отвечать быстро.
- Долгая работа (AI) — только в Celery.

POST /api/v1/ai/recognize/
- создаёт Meal (meal_type/date обязательны по модели)
- если прислали multipart file — сохраняем фото в Meal.photo
- запускает Celery задачу и возвращает 202 + task_id

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
    Вход: {image, meal_type, date, user_comment}
    Выход: 202 {task_id, status: 'processing'}
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
        date = s.validated_data["date"]
        user_comment = s.validated_data.get("user_comment", "")

        # P1-4: Проверяем лимит ДО создания Meal (избегаем orphan meals)
        from apps.billing.services import get_effective_plan_for_user
        from apps.billing.usage import DailyUsage

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

        # 1) Async — основной режим (быстро и безопасно)
        if getattr(settings, "AI_ASYNC_ENABLED", True):
            task = recognize_food_async.delay(
                meal_id=None,  # P1-1: Don't create Meal yet
                meal_type=meal_type,
                date=date,
                image_bytes=normalized.bytes_data,
                mime_type=normalized.mime_type,
                user_comment=user_comment,
                request_id=request_id,
                user_id=request.user.id,
            )

            # P0 Security Check: link task to user in cache (24h TTL)
            cache.set(f"ai_task_owner:{task.id}", request.user.id, timeout=86400)

            data = {"task_id": str(task.id), "meal_id": None, "status": "processing"}
            resp = Response(data, status=status.HTTP_202_ACCEPTED)
            resp["X-Request-ID"] = request_id
            return resp

        # 2) Sync — только для dev (не включать в проде)
        result = recognize_food_async.apply(
            kwargs=dict(
                meal_id=None,
                meal_type=meal_type,
                date=date,
                image_bytes=normalized.bytes_data,
                mime_type=normalized.mime_type,
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
                "error": "AI processing failed",
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

        logger.info(
            "[AI] Task cancelled: task_id=%s user_id=%s rid=%s",
            task_id,
            request.user.id,
            request_id,
        )

        return Response({"ok": True}, status=status.HTTP_200_OK)

