"""
Интеграция с Django API для отправки результатов AI теста.
"""

import httpx
import re
from typing import Optional, Dict, Any
from datetime import datetime

from app.config import settings
from app.utils.logger import logger


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
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                timeout=10.0
            )
            response.raise_for_status()

            result = response.json()
            logger.info(
                f"✅ Test results saved to Django: "
                f"telegram_id={telegram_id}, user_id={result.get('user_id')}"
            )
            return result

    except httpx.HTTPStatusError as e:
        logger.error(
            f"❌ Django API returned error {e.response.status_code}: "
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
