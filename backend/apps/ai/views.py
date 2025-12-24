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
from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.nutrition.models import Meal

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

    Всегда стараемся работать async (202).
    Sync режим можно оставить только для дев-отладки.
    """

    throttle_classes = [AIRecognitionPerMinuteThrottle, AIRecognitionPerDayThrottle]

    def post(self, request, *args, **kwargs):
        request_id = _new_request_id()

        s = AIRecognizeRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        normalized = s.validated_data["normalized_image"]
        meal_type = s.validated_data["meal_type"]
        date = s.validated_data["date"]
        user_comment = s.validated_data.get("user_comment", "")
        source_type = s.validated_data.get("source_type", "unknown")

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

        # 1) Создаём Meal (meal_type/date обязательны)
        with transaction.atomic():
            meal = Meal.objects.create(
                user=request.user,
                meal_type=meal_type,
                date=date,
            )

            # Если пришёл multipart file — сохраняем фото как есть (самый правильный путь)
            # Для data_url фото в модель можно тоже сохранять через ContentFile,
            # но это не обязательно для MVP (и добавляет лишние нюансы).
            if source_type == "file":
                img_file = s.validated_data.get("image")
                if img_file:
                    meal.photo = img_file
                    meal.save(update_fields=["photo"])

        # 2) Async — основной режим (быстро и безопасно)
        if getattr(settings, "AI_ASYNC_ENABLED", True):
            task = recognize_food_async.delay(
                meal_id=meal.id,
                image_bytes=normalized.bytes_data,
                mime_type=normalized.mime_type,
                user_comment=user_comment,
                request_id=request_id,
                user_id=request.user.id,
            )
            data = {"task_id": str(task.id), "meal_id": meal.id, "status": "processing"}
            resp = Response(data, status=status.HTTP_202_ACCEPTED)
            resp["X-Request-ID"] = request_id
            return resp

        # 3) Sync — только для dev (не включать в проде)
        result = recognize_food_async.apply(
            kwargs=dict(
                meal_id=meal.id,
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
    Возвращает состояние и результат задачи.
    """

    throttle_classes = [TaskStatusThrottle]

    def get(self, request, task_id: str, *args, **kwargs):
        request_id = _new_request_id()

        res = AsyncResult(task_id)
        state = (res.state or "").upper()

        if state in {"PENDING", "STARTED", "RETRY"}:
            data = {"task_id": task_id, "status": "processing", "state": state}
            resp = Response(data, status=status.HTTP_200_OK)
            resp["X-Request-ID"] = request_id
            return resp

        if state == "SUCCESS":
            payload: Dict[str, Any] = res.result or {}
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

        data = {"task_id": task_id, "status": "unknown", "state": state}
        resp = Response(data, status=status.HTTP_200_OK)
        resp["X-Request-ID"] = request_id
        return resp
