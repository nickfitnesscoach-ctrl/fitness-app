"""
Валидаторы для опроса Personal Plan.
"""

import re
import pytz
from typing import Optional

from app.constants import VALIDATION_LIMITS, UTC_TO_IANA_MAPPING

# Маппинг популярных регионов, стран и городов на IANA timezones
COUNTRY_CITY_TO_IANA = {
    # Регионы (русские названия)
    "европа": "Europe/Paris",
    "америка": "America/New_York",
    "азия": "Asia/Tokyo",

    # Страны и города (русские названия)
    "испания": "Europe/Madrid",
    "мадрид": "Europe/Madrid",
    "барселона": "Europe/Madrid",
    "россия": "Europe/Moscow",
    "москва": "Europe/Moscow",
    "санкт-петербург": "Europe/Moscow",
    "питер": "Europe/Moscow",
    "германия": "Europe/Berlin",
    "берлин": "Europe/Berlin",
    "франция": "Europe/Paris",
    "париж": "Europe/Paris",
    "англия": "Europe/London",
    "лондон": "Europe/London",
    "сша": "America/New_York",
    "нью-йорк": "America/New_York",
    "италия": "Europe/Rome",
    "рим": "Europe/Rome",
    "япония": "Asia/Tokyo",
    "токио": "Asia/Tokyo",
    "китай": "Asia/Shanghai",
    "пекин": "Asia/Shanghai",
    "индия": "Asia/Kolkata",
    "дубай": "Asia/Dubai",
    "казахстан": "Asia/Almaty",
    "астана": "Asia/Almaty",
    "алматы": "Asia/Almaty",
    "украина": "Europe/Kyiv",
    "киев": "Europe/Kyiv",
    "беларусь": "Europe/Minsk",
    "минск": "Europe/Minsk",
    "турция": "Europe/Istanbul",
    "стамбул": "Europe/Istanbul",
    "грузия": "Asia/Tbilisi",
    "тбилиси": "Asia/Tbilisi",
    "армения": "Asia/Yerevan",
    "ереван": "Asia/Yerevan",
    "азербайджан": "Asia/Baku",
    "баку": "Asia/Baku",
}


def validate_age(text: str) -> Optional[int]:
    """
    Валидирует возраст пользователя.

    Args:
        text: Введённый текст

    Returns:
        Возраст (int) или None если валидация провалена
    """
    try:
        age = int(text.strip())
        limits = VALIDATION_LIMITS["age"]
        if limits["min"] <= age <= limits["max"]:
            return age
    except (ValueError, KeyError):
        pass
    return None


def validate_height(text: str) -> Optional[int]:
    """
    Валидирует рост пользователя (в см).

    Args:
        text: Введённый текст

    Returns:
        Рост (int) или None если валидация провалена
    """
    try:
        height = int(text.strip())
        limits = VALIDATION_LIMITS["height_cm"]
        if limits["min"] <= height <= limits["max"]:
            return height
    except (ValueError, KeyError):
        pass
    return None


def validate_weight(text: str) -> Optional[float]:
    """
    Валидирует вес пользователя (в кг).

    Args:
        text: Введённый текст (может быть дробным числом)

    Returns:
        Вес (float) или None если валидация провалена
    """
    try:
        # Заменить запятую на точку (для европейского формата)
        text_normalized = text.strip().replace(',', '.')
        weight = float(text_normalized)
        limits = VALIDATION_LIMITS["weight_kg"]
        if limits["min"] <= weight <= limits["max"]:
            return weight
    except (ValueError, KeyError):
        pass
    return None


def validate_target_weight(text: str, current_weight: float) -> Optional[float]:
    """
    Валидирует целевой вес пользователя.

    Args:
        text: Введённый текст
        current_weight: Текущий вес пользователя

    Returns:
        Целевой вес (float) или None если валидация провалена
    """
    target = validate_weight(text)
    if target is None:
        return None

    # Целевой вес должен отличаться от текущего
    if abs(target - current_weight) < 0.1:  # Разница менее 100 грамм
        return None

    return target


def validate_iana_tz(tz_name: str) -> bool:
    """
    Проверяет корректность IANA timezone.

    Args:
        tz_name: Название часового пояса (например, "Europe/Paris")

    Returns:
        True если timezone валиден, иначе False
    """
    try:
        pytz.timezone(tz_name)
        return True
    except pytz.UnknownTimeZoneError:
        return False


def parse_utc_offset(text: str) -> Optional[int]:
    """
    Парсит UTC offset из строки вида "UTC+3" или "UTC-5".

    Args:
        text: Введённая строка

    Returns:
        Offset в часах (int) или None если формат некорректен
    """
    match = re.match(r'^UTC([+-]?\d{1,2})$', text.strip(), re.IGNORECASE)
    if match:
        try:
            offset = int(match.group(1))
            # Ограничение: от -12 до +14 (самые крайние часовые пояса)
            if -12 <= offset <= 14:
                return offset
        except ValueError:
            pass
    return None


def map_utc_to_iana(offset_hours: int) -> str:
    """
    Маппинг UTC±N на популярные IANA timezones.

    Args:
        offset_hours: Offset в часах (например, +3 для UTC+3)

    Returns:
        IANA timezone или Etc/GMT формат
    """
    if offset_hours in UTC_TO_IANA_MAPPING:
        return UTC_TO_IANA_MAPPING[offset_hours]

    # Fallback: использовать Etc/GMT
    # ВАЖНО: Etc/GMT имеет инвертированный знак!
    # UTC+3 → Etc/GMT-3
    return f"Etc/GMT{-offset_hours:+d}"


def get_utc_offset_minutes(tz_name: str) -> int:
    """
    Вычисляет текущий UTC offset в минутах для заданного часового пояса.
    Учитывает DST (летнее время).

    Args:
        tz_name: IANA timezone (например, "Europe/Paris")

    Returns:
        Offset в минутах (например, 60 для UTC+1)
    """
    try:
        from datetime import datetime
        tz = pytz.timezone(tz_name)
        now = datetime.now(tz)
        offset_seconds = now.utcoffset().total_seconds()
        return int(offset_seconds / 60)
    except Exception:
        # Fallback: попытаться распарсить из названия зоны
        return 0


def validate_and_normalize_timezone(text: str) -> Optional[tuple[str, int]]:
    """
    Валидирует и нормализует введённый часовой пояс.

    Args:
        text: Введённая строка (IANA, UTC±N, или название страны/города)

    Returns:
        Кортеж (iana_timezone, offset_minutes) или None если невалидно
    """
    text = text.strip()

    # Попытка 1: IANA timezone
    if validate_iana_tz(text):
        offset_minutes = get_utc_offset_minutes(text)
        return (text, offset_minutes)

    # Попытка 2: UTC±N формат
    offset_hours = parse_utc_offset(text)
    if offset_hours is not None:
        iana_tz = map_utc_to_iana(offset_hours)
        offset_minutes = offset_hours * 60
        return (iana_tz, offset_minutes)

    # Попытка 3: Название страны или города (на английском или русском)
    text_lower = text.lower()
    if text_lower in COUNTRY_CITY_TO_IANA:
        iana_tz = COUNTRY_CITY_TO_IANA[text_lower]
        offset_minutes = get_utc_offset_minutes(iana_tz)
        return (iana_tz, offset_minutes)

    return None
