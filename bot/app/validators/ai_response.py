"""
Валидация ответов ИИ-агента.
"""

import re
from typing import Dict, List, Any


def validate_ai_response(text: str) -> Dict[str, Any]:
    """
    Проверяет наличие обязательных элементов в ответе ИИ.

    Args:
        text: Текст ответа от ИИ-агента

    Returns:
        Словарь: {"valid": bool, "errors": list}
    """
    errors: List[str] = []

    # 0. Проверка длины ответа (Telegram limit 4096, делаем запас)
    MAX_LENGTH = 4000
    if len(text) > MAX_LENGTH:
        errors.append(f"Ответ слишком длинный: {len(text)} символов (лимит {MAX_LENGTH})")

    # 0.1. Проверка минимальной длины
    MIN_LENGTH = 200
    if len(text) < MIN_LENGTH:
        errors.append(f"Ответ слишком короткий: {len(text)} символов (минимум {MIN_LENGTH})")

    # 0.2. Проверка на запрещённые слова (добавки, препараты)
    forbidden_words = ["добавк", "препарат", "лекарств", "витамин", "бад"]
    found_forbidden = []
    for word in forbidden_words:
        if word in text.lower():
            found_forbidden.append(word)
    if found_forbidden:
        errors.append(f"Обнаружены запрещённые слова: {', '.join(found_forbidden)}")

    # 1. Проверка наличия диапазона калорий
    # Паттерн: ≈ 1400–1600 ккал/сут (или вариации с дефисами)
    calorie_pattern = r'≈?\s*\d{3,5}\s*[–—-]\s*\d{3,5}\s*ккал'
    if not re.search(calorie_pattern, text):
        errors.append("Отсутствует диапазон калорий (формат: ≈ X–Y ккал/сут)")

    # 2. Проверка обязательной фразы про тренера
    disclaimer_pattern = r'[Тт]очные цифры индивидуальны.{0,20}для точного расчёта обратитесь к тренеру'
    if not re.search(disclaimer_pattern, text, re.IGNORECASE | re.DOTALL):
        errors.append("Отсутствует фраза про индивидуальный расчёт и тренера")

    # 3. Проверка на запрещённые паттерны (точные граммы БЖУ)
    # Примеры запрещённых: "120 г белка", "белки: 100 г"
    exact_macros_pattern = r'(?:белк|жир|углевод)[а-яё]*\s*:?\s*\d+\s*г(?:\s|$|,|\.)'
    if re.search(exact_macros_pattern, text, re.IGNORECASE):
        errors.append("ИИ указал точные граммы БЖУ (запрещено, допустимы только диапазоны)")

    # 4. Дополнительная проверка: наличие блоков (хотя бы некоторых ключевых слов)
    required_keywords = ["тренировки", "питание", "активность"]
    missing_keywords = [kw for kw in required_keywords if kw.lower() not in text.lower()]
    if missing_keywords:
        errors.append(f"Отсутствуют ключевые блоки: {', '.join(missing_keywords)}")

    return {
        "valid": len(errors) == 0,
        "errors": errors
    }


def extract_calorie_range(text: str) -> tuple[int, int] | None:
    """
    Извлекает диапазон калорий из текста ответа ИИ.

    Args:
        text: Текст ответа от ИИ

    Returns:
        Кортеж (min_cal, max_cal) или None если не найдено
    """
    pattern = r'≈?\s*(\d{3,5})\s*[–—-]\s*(\d{3,5})\s*ккал'
    match = re.search(pattern, text)
    if match:
        try:
            min_cal = int(match.group(1))
            max_cal = int(match.group(2))
            return (min_cal, max_cal)
        except ValueError:
            pass
    return None
