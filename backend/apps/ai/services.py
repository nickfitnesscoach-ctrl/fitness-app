"""
Cancel service layer для обработки отмены AI задач.

Responsibilities:
- Structured logging для всех cancel событий
- Создание CancelEvent в БД (audit trail)
- Обновление MealPhoto.status = CANCELLED
- Отзыв Celery tasks (best-effort)
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from celery import current_app as celery_app
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from apps.nutrition.models import CancelEvent, Meal, MealPhoto

User = get_user_model()
logger = logging.getLogger(__name__)


class CancelService:
    """
    Service для обработки cancel запросов от frontend.

    Обеспечивает:
    - Идемпотентность (через unique client_cancel_id)
    - Structured logging (всегда фиксируем cancel)
    - Best-effort отмену (если нечего отменять → noop=true)
    """

    def __init__(self, user: User, request_id: Optional[str] = None):
        """
        Args:
            user: Пользователь, отправивший cancel
            request_id: X-Request-ID для корреляции логов (опционально)
        """
        self.user = user
        self.request_id = request_id or "unknown"

    def process_cancel(
        self,
        client_cancel_id: UUID,
        run_id: Optional[int] = None,
        meal_id: Optional[int] = None,
        meal_photo_ids: Optional[List[int]] = None,
        task_ids: Optional[List[str]] = None,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Обработать cancel запрос.

        Args:
            client_cancel_id: UUID от фронта (для идемпотентности)
            run_id: Frontend run identifier
            meal_id: ID приёма пищи для отмены
            meal_photo_ids: Список ID фото для отмены
            task_ids: Список Celery task IDs для отзыва
            reason: Причина отмены (user_cancel, timeout, etc.)

        Returns:
            Dict с результатом:
            {
                "status": "ok" | "error",
                "cancel_received": True,
                "cancelled_tasks": 1,
                "updated_photos": 2,
                "noop": False,
                "message": "Cancel processed"
            }

        Raises:
            Exception: При критических ошибках (не ловим здесь, пусть views обработает)
        """
        meal_photo_ids = meal_photo_ids or []
        task_ids = task_ids or []

        # Structured logging (ВСЕГДА пишем, даже если noop)
        logger.info(
            "[AI][Cancel] RECEIVED user=%s client_cancel_id=%s run_id=%s meal_id=%s "
            "meal_photo_ids=%d task_ids=%d request_id=%s reason=%s",
            self.user.id,
            client_cancel_id,
            run_id,
            meal_id,
            len(meal_photo_ids),
            len(task_ids),
            self.request_id,
            reason or "not_specified",
        )

        # Проверка идемпотентности
        existing_event = CancelEvent.objects.filter(client_cancel_id=client_cancel_id).first()
        if existing_event:
            logger.info(
                "[AI][Cancel] DUPLICATE client_cancel_id=%s (already processed), returning cached result",
                client_cancel_id,
            )
            return {
                "status": "ok",
                "cancel_received": True,
                "cancelled_tasks": existing_event.cancelled_tasks,
                "updated_photos": existing_event.updated_photos,
                "noop": existing_event.noop,
                "message": "Cancel already processed (idempotent)",
            }

        # Обработка cancel
        cancelled_tasks = self._revoke_tasks(task_ids)
        updated_photos = self._update_photos(meal_photo_ids, meal_id)

        noop = cancelled_tasks == 0 and updated_photos == 0

        # Сохранить CancelEvent в БД (audit trail)
        payload = {
            "run_id": run_id,
            "meal_id": meal_id,
            "meal_photo_ids": meal_photo_ids,
            "task_ids": task_ids,
            "reason": reason,
        }

        # Проверить существование meal перед сохранением (race-safe)
        meal_instance = None
        if meal_id:
            try:
                meal_instance = Meal.objects.filter(id=meal_id, user=self.user).first()
                if not meal_instance:
                    # P1 MONITORING: Track MEAL_MISSING frequency
                    # If this metric spikes → investigate early delete logic or race conditions
                    logger.warning(
                        "[AI][Cancel] MEAL_MISSING meal_id=%s user=%s (deleted or not owned)",
                        meal_id,
                        self.user.id,
                    )
            except Exception as e:
                logger.warning(
                    "[AI][Cancel] MEAL_LOOKUP_ERROR meal_id=%s error=%s",
                    meal_id,
                    str(e),
                    exc_info=True,
                )

        try:
            with transaction.atomic():
                cancel_event = CancelEvent.objects.create(
                    user=self.user,
                    client_cancel_id=client_cancel_id,
                    run_id=run_id,
                    meal=meal_instance,  # None if meal not found
                    payload=payload,
                    cancelled_tasks=cancelled_tasks,
                    updated_photos=updated_photos,
                    noop=noop,
                )
                logger.info(
                    "[AI][Cancel] EVENT_SAVED id=%s user=%s client_cancel_id=%s meal=%s noop=%s",
                    cancel_event.id,
                    self.user.id,
                    client_cancel_id,
                    meal_instance.id if meal_instance else "None",
                    noop,
                )
        except IntegrityError:
            # Race condition: другой запрос успел создать событие с этим client_cancel_id
            logger.warning(
                "[AI][Cancel] RACE_CONDITION client_cancel_id=%s (another request won), fetching existing",
                client_cancel_id,
            )
            existing_event = CancelEvent.objects.get(client_cancel_id=client_cancel_id)
            return {
                "status": "ok",
                "cancel_received": True,
                "cancelled_tasks": existing_event.cancelled_tasks,
                "updated_photos": existing_event.updated_photos,
                "noop": existing_event.noop,
                "message": "Cancel already processed (race condition)",
            }

        # Логирование результата
        if noop:
            logger.info(
                "[AI][Cancel] NOOP user=%s client_cancel_id=%s (no active tasks/photos to cancel)",
                self.user.id,
                client_cancel_id,
            )
        else:
            logger.info(
                "[AI][Cancel] PROCESSED user=%s client_cancel_id=%s cancelled_tasks=%d updated_photos=%d",
                self.user.id,
                client_cancel_id,
                cancelled_tasks,
                updated_photos,
            )

        return {
            "status": "ok",
            "cancel_received": True,
            "cancelled_tasks": cancelled_tasks,
            "updated_photos": updated_photos,
            "noop": noop,
            "message": "Cancel processed successfully" if not noop else "Cancel received (no active tasks)",
        }

    def _revoke_tasks(self, task_ids: List[str]) -> int:
        """
        Отозвать Celery tasks (best-effort).

        Args:
            task_ids: Список Celery task IDs

        Returns:
            Количество успешно отозванных задач
        """
        if not task_ids:
            return 0

        revoked_count = 0
        for task_id in task_ids:
            try:
                celery_app.control.revoke(task_id, terminate=True, signal="SIGKILL")
                revoked_count += 1
                logger.info("[AI][Cancel] REVOKED task_id=%s", task_id)
            except Exception as e:
                logger.warning(
                    "[AI][Cancel] REVOKE_FAILED task_id=%s error=%s", task_id, str(e), exc_info=True
                )

        return revoked_count

    def _update_photos(self, meal_photo_ids: List[int], meal_id: Optional[int] = None) -> int:
        """
        Установить MealPhoto.status = CANCELLED для указанных фото.

        Args:
            meal_photo_ids: Список ID фото для отмены
            meal_id: ID приёма пищи (для дополнительной валидации)

        Returns:
            Количество обновлённых фото
        """
        if not meal_photo_ids:
            return 0

        # Базовая защита: обновляем только фото текущего пользователя
        queryset = MealPhoto.objects.filter(
            id__in=meal_photo_ids, meal__user=self.user
        ).exclude(status__in=["SUCCESS", "FAILED", "CANCELLED"])

        # Если передан meal_id — дополнительная проверка
        if meal_id:
            queryset = queryset.filter(meal_id=meal_id)

        with transaction.atomic():
            updated = queryset.select_for_update().update(status="CANCELLED")

        if updated > 0:
            logger.info(
                "[AI][Cancel] UPDATED_PHOTOS count=%d meal_photo_ids=%s user=%s",
                updated,
                meal_photo_ids,
                self.user.id,
            )

        return updated
