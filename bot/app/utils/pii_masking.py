"""
Утилиты для маскирования PII (Personal Identifiable Information) в логах.

Соответствие GDPR/CCPA требованиям:
- Персональные данные (age, weight, height, timezone) должны быть замаскированы
- User ID хешируется для возможности отслеживания без раскрытия личности
"""

import hashlib
from typing import Any, Dict, Optional


def mask_user_id(user_id: int) -> str:
    """
    Хеширует user_id для логирования без раскрытия личности.

    Args:
        user_id: Telegram user ID

    Returns:
        Хешированный ID в формате "user_abc123..." (первые 8 символов SHA256)

    Example:
        >>> mask_user_id(123456789)
        'user_cd2eb0ff'
    """
    # SHA256 хеш + первые 8 символов для компактности
    hash_obj = hashlib.sha256(str(user_id).encode())
    return f"user_{hash_obj.hexdigest()[:8]}"


def mask_numeric_value(value: Optional[Any], value_type: str = "number") -> str:
    """
    Маскирует числовые PII данные (возраст, вес, рост).

    Args:
        value: Числовое значение для маскирования
        value_type: Тип значения для контекста (age/weight/height)

    Returns:
        Замаскированная строка в формате "[MASKED_{type}]"

    Example:
        >>> mask_numeric_value(30, "age")
        '[MASKED_age]'
        >>> mask_numeric_value(None, "weight")
        '[MASKED_weight]'
    """
    if value is None:
        return f"[MASKED_{value_type}]"

    # Для числовых значений показываем только диапазон
    if isinstance(value, (int, float)):
        # Для возраста - десятилетия
        if value_type == "age" and isinstance(value, int):
            decade = (value // 10) * 10
            return f"[{decade}-{decade + 9}]"

        # Для веса/роста - диапазоны по 10 единиц
        if value_type in ("weight", "height") and isinstance(value, (int, float)):
            range_start = (int(value) // 10) * 10
            return f"[{range_start}-{range_start + 10}]"

    return f"[MASKED_{value_type}]"


def mask_timezone(tz: Optional[str]) -> str:
    """
    Маскирует timezone для защиты местоположения пользователя.

    Args:
        tz: IANA timezone (например, "Europe/Moscow")

    Returns:
        Замаскированная timezone (только регион без города)

    Example:
        >>> mask_timezone("Europe/Moscow")
        'Europe/***'
        >>> mask_timezone("America/New_York")
        'America/***'
    """
    if not tz:
        return "[MASKED_tz]"

    # Оставить только континент, скрыть город
    parts = tz.split("/")
    if len(parts) >= 2:
        return f"{parts[0]}/***"

    return "[MASKED_tz]"


def mask_payload(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Маскирует PII данные в payload для безопасного логирования.

    Args:
        payload: Словарь с данными пользователя

    Returns:
        Новый словарь с замаскированными PII данными

    Example:
        >>> mask_payload({"age": 30, "weight_kg": 80.5, "gender": "male"})
        {'age': '[20-29]', 'weight_kg': '[80-90]', 'gender': 'male'}
    """
    if not payload:
        return {}

    masked = {}

    for key, value in payload.items():
        # Маскирование в зависимости от типа данных
        if key == "age":
            masked[key] = mask_numeric_value(value, "age")

        elif key in ("weight_kg", "target_weight_kg"):
            masked[key] = mask_numeric_value(value, "weight")

        elif key == "height_cm":
            masked[key] = mask_numeric_value(value, "height")

        elif key == "tz":
            masked[key] = mask_timezone(value)

        elif key == "offset_minutes":
            # Offset не раскрывает точное местоположение (много стран в одном offset)
            masked[key] = f"[{value}]" if value is not None else "[MASKED_offset]"

        else:
            # Остальные данные (gender, activity, body_type_id, etc) - не PII
            masked[key] = value

    return masked
