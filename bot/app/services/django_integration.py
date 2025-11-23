"""
Интеграция с Django API для отправки результатов AI теста.
"""

import logging
import httpx
import re
from typing import Optional, Dict, Any

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    retry_if_exception,
    before_sleep_log,
    RetryError
)

from app.config import settings
from app.utils.logger import logger


def _is_retryable_http_error(exception: Exception) -> bool:
    """
    Определяет, стоит ли делать retry для данного исключения.
    """
    if not isinstance(exception, httpx.HTTPStatusError):
        return False

    retryable_codes = {
        429,  # Too Many Requests
        502,  # Bad Gateway
        503,  # Service Unavailable
        504,  # Gateway Timeout
    }
    return exception.response.status_code in retryable_codes


@retry(
    stop=stop_after_attempt(settings.DJANGO_RETRY_ATTEMPTS),
    wait=wait_exponential(
        multiplier=settings.DJANGO_RETRY_MULTIPLIER,
        min=settings.DJANGO_RETRY_MIN_WAIT,
        max=settings.DJANGO_RETRY_MAX_WAIT
    ),
    retry=retry_if_exception_type(httpx.HTTPStatusError) & retry_if_exception(_is_retryable_http_error),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True
)
async def _make_django_request(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    HTTP POST запрос к Django API с автоматическим retry.

    Args:
        url: URL для POST запроса
        payload: JSON данные

    Returns:
        JSON ответ от API

    Raises:
        httpx.HTTPStatusError: При HTTP ошибках (после всех retry попыток)
        httpx.TimeoutException: При таймауте запроса
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            json=payload,
            timeout=10.0
        )
        response.raise_for_status()
        return response.json()


def parse_range_value(value) -> Optional[float]:
    """
    Извлекает среднее значение из диапазона или возвращает само значение.
    
    Примеры:
        "[20-29]" -> 24.5
        "[170-180]" -> 175.0
        "75" -> 75.0
        75 -> 75.0
    """
    if not value:
        return None
    
    # Если это уже число
    if isinstance(value, (int, float)):
        return float(value)
    
    # Если это строка с диапазоном [min-max]
    value_str = str(value)
    match = re.match(r'\[(\d+)-(\d+)\]', value_str)
    if match:
        min_val = float(match.group(1))
        max_val = float(match.group(2))
        return (min_val + max_val) / 2
    
    # Попытка преобразовать в число
    try:
        return float(value_str)
    except:
        return None


async def send_test_results_to_django(
    telegram_id: int,
    first_name: str,
    last_name: Optional[str],
    username: Optional[str],
    survey_data: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Отправляет результаты AI теста в Django API.

    Args:
        telegram_id: ID пользователя в Telegram
        first_name: Имя пользователя
        last_name: Фамилия пользователя (опционально)
        username: Username в Telegram (опционально)
        survey_data: Данные опроса (gender, age, weight, height, activity, goal, target_weight_kg, tz,
                     training_level, goals, health_restrictions, body types)

    Returns:
        Dict с результатом сохранения или None при ошибке

    Note:
        Отправляются только данные опроса. КБЖУ и AI план назначаются тренером в панели управления.
    """
    # Получаем URL Django API из настроек
    django_api_url = getattr(settings, 'DJANGO_API_URL', None)

    # Если URL не настроен, логируем и возвращаем None
    if not django_api_url:
        logger.warning("DJANGO_API_URL not configured, skipping Django integration")
        return None

    url = f"{django_api_url}/telegram/save-test/"

    # Парсим числовые значения (могут быть диапазонами типа "[20-29]")
    age = parse_range_value(survey_data.get("age"))
    weight_kg = parse_range_value(survey_data.get("weight_kg"))
    height_cm = parse_range_value(survey_data.get("height_cm"))
    target_weight_kg = parse_range_value(survey_data.get("target_weight_kg"))

    # Маппинг activity levels: бот → Django
    activity_mapping = {
        "sedentary": "minimal",
        "light": "low",
        "moderate": "medium",
        "active": "high"
    }

    activity_value = survey_data.get("activity", "moderate")
    mapped_activity = activity_mapping.get(activity_value, "medium")

    # Преобразуем данные опроса в формат Django
    answers = {
        "age": int(age) if age else None,
        "gender": survey_data.get("gender"),
        "weight": float(weight_kg) if weight_kg else 0,
        "height": int(height_cm) if height_cm else 0,
        "activity_level": mapped_activity,
        "goal": survey_data.get("goal", "maintenance"),
        "target_weight": float(target_weight_kg) if target_weight_kg else None,
        "timezone": survey_data.get("tz"),
        "training_level": survey_data.get("training_level"),
        "goals": survey_data.get("body_goals", []),
        "health_restrictions": survey_data.get("health_limitations", []),
        "current_body_type": survey_data.get("body_now_id"),
        "ideal_body_type": survey_data.get("body_ideal_id")
    }

    payload = {
        "telegram_id": telegram_id,
        "first_name": first_name,
        "last_name": last_name or "",
        "username": username or "",
        "answers": answers
    }

    try:
        result = await _make_django_request(url, payload)
        logger.info(
            f"✅ Test results saved to Django: "
            f"telegram_id={telegram_id}, user_id={result.get('user_id')}"
        )
        return result

    except RetryError as e:
        original_exception = e.last_attempt.exception()
        if isinstance(original_exception, httpx.HTTPStatusError):
            logger.error(
                f"❌ Django API HTTP error {original_exception.response.status_code} "
                f"(after {settings.DJANGO_RETRY_ATTEMPTS} retries): "
                f"{original_exception.response.text} for telegram_id={telegram_id}"
            )
        else:
            logger.error(
                f"❌ Django API failed after {settings.DJANGO_RETRY_ATTEMPTS} retries "
                f"for telegram_id={telegram_id}: {original_exception}"
            )
        return None

    except httpx.HTTPStatusError as e:
        # Не-retryable HTTP ошибки (4xx кроме 429)
        logger.error(
            f"❌ Django API error {e.response.status_code} (non-retryable): "
            f"{e.response.text} for telegram_id={telegram_id}"
        )
        return None

    except httpx.TimeoutException:
        logger.error(
            f"❌ Django API timeout for telegram_id={telegram_id}"
        )
        return None

    except Exception as e:
        logger.error(
            f"❌ Unexpected error sending to Django for telegram_id={telegram_id}: {e}",
            exc_info=True
        )
        return None
