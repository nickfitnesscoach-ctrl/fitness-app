"""
Сервис для логирования событий в БД (опционально).
"""

from typing import Optional, Dict, Any
from datetime import datetime

from app.utils.logger import logger
from app.utils.pii_masking import mask_user_id, mask_payload


class EventLogger:
    """
    Логирование событий для аналитики.

    На первом этапе - просто логирование в файл.
    В будущем можно добавить запись в БД (таблица events).
    """

    @staticmethod
    def log_event(
        user_id: int,
        event: str,
        payload: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Логирует событие пользователя с маскированием PII данных.

        Args:
            user_id: ID пользователя (будет хеширован для логов)
            event: Название события (например, "survey_started")
            payload: Дополнительные данные (PII данные будут замаскированы)

        Note:
            Для соответствия GDPR/CCPA:
            - user_id хешируется (SHA256, первые 8 символов)
            - Персональные данные (age, weight, height, tz) маскируются
            - Не-PII данные (gender, activity) остаются без изменений
        """
        # Маскирование user_id для защиты личности
        masked_user_id = mask_user_id(user_id)

        # Маскирование PII в payload
        masked_payload = mask_payload(payload) if payload else {}

        log_data = {
            "user_id": masked_user_id,
            "event": event,
            "timestamp": datetime.now().isoformat(),
            "payload": masked_payload
        }

        # Логирование с замаскированными данными
        logger.info(f"EVENT: {event} | User: {masked_user_id} | Data: {masked_payload}")

        # TODO: В будущем - запись в таблицу events:
        # async with async_session() as session:
        #     event_record = Event(
        #         user_id=user_id,
        #         event=event,
        #         payload=payload,
        #         ts=datetime.now()
        #     )
        #     session.add(event_record)
        #     await session.commit()


# Глобальный экземпляр
event_logger = EventLogger()


# Хелперы для частых событий
def log_survey_started(user_id: int) -> None:
    """Логирует начало опроса."""
    event_logger.log_event(user_id, "survey_started")


def log_survey_step_completed(user_id: int, step_name: str, data: Optional[Dict] = None) -> None:
    """Логирует завершение шага опроса."""
    event_logger.log_event(
        user_id,
        f"survey_step_completed:{step_name}",
        payload=data
    )


def log_survey_cancelled(user_id: int, last_step: Optional[str] = None) -> None:
    """Логирует отмену опроса."""
    event_logger.log_event(
        user_id,
        "survey_cancelled",
        payload={"last_step": last_step}
    )


def log_survey_completed(user_id: int) -> None:
    """Логирует успешное завершение опроса."""
    event_logger.log_event(user_id, "survey_completed")


def log_plan_generated(user_id: int, model: str, validation_passed: bool) -> None:
    """Логирует генерацию плана."""
    event_logger.log_event(
        user_id,
        "plan_generated",
        payload={"model": model, "validation_passed": validation_passed}
    )


def log_ai_error(user_id: int, error_type: str, error_message: str) -> None:
    """Логирует ошибку при работе с ИИ."""
    event_logger.log_event(
        user_id,
        "ai_error",
        payload={"error_type": error_type, "error_message": error_message}
    )
