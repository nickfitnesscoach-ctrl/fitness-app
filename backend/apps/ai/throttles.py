"""
throttles.py — ограничения частоты запросов (антиспам/анти-DoS).

Простыми словами:
- чтобы один человек не “завалил” сервер частыми запросами
- это НЕ тарифы (Free/Pro), это защита инфраструктуры

Важно:
- scope должен совпадать с ключом в settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
"""

from __future__ import annotations

from rest_framework.throttling import UserRateThrottle


class AIRecognitionPerMinuteThrottle(UserRateThrottle):
    """
    Ограничение распознаваний в минуту.

    Используется на POST /ai/recognize/
    """

    scope = "ai_per_minute"


class AIRecognitionPerDayThrottle(UserRateThrottle):
    """
    Ограничение распознаваний в день.

    Используется на POST /ai/recognize/
    """

    scope = "ai_per_day"


class TaskStatusThrottle(UserRateThrottle):
    """
    Ограничение polling эндпоинта статуса задачи.

    Используется на GET /ai/task/<task_id>/
    """

    scope = "task_status"
