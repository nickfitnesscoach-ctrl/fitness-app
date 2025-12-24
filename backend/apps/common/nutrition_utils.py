"""
apps/common/nutrition_utils.py

Общие утилиты для работы с нутриционными данными.

Используется в:
- apps/ai/tasks.py
- apps/ai_proxy/adapter.py
"""

from __future__ import annotations

from typing import Any


def clamp_grams(value: Any, min_value: int = 1) -> int:
    """
    Гарантирует, что граммовка >= min_value.

    FoodItem.grams имеет MinValueValidator(1), поэтому
    значения 0/None/мусор нужно приводить к min_value.

    Args:
        value: Значение для преобразования (может быть int, float, str, None)
        min_value: Минимально допустимое значение (default: 1)

    Returns:
        int: Граммовка >= min_value

    Examples:
        >>> clamp_grams(100)
        100
        >>> clamp_grams(0)
        1
        >>> clamp_grams(None)
        1
        >>> clamp_grams("invalid")
        1
    """
    try:
        g = int(round(float(value)))
    except (TypeError, ValueError):
        g = min_value
    return min_value if g < min_value else g
