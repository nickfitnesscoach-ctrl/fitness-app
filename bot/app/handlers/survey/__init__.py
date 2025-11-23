"""
Пакет хендлеров для опроса Personal Plan.

Организация:
- commands.py: Команды /start, /personal_plan и начало опроса
- gender.py: Выбор пола
- metrics.py: Ввод метрических данных (возраст, рост, вес, целевой вес)
- activity.py: Выбор уровня активности
- body_types.py: Выбор текущего и идеального типа фигуры
- timezone.py: Выбор часового пояса
- confirmation.py: Подтверждение данных и генерация плана
- navigation.py: Навигация (отмена, возврат назад)
- helpers.py: Вспомогательные функции
"""

from aiogram import Router

from . import (
    commands,
    gender,
    metrics,
    activity,
    training_goals,
    health,
    body_types,
    timezone,
    confirmation,
    navigation
)

# Создать главный роутер для опроса Personal Plan
router = Router(name="personal_plan")

# Включить все под-роутеры в порядке приоритета
# Порядок важен: более специфичные фильтры должны быть выше
router.include_router(commands.router)
router.include_router(gender.router)
router.include_router(metrics.router)
router.include_router(activity.router)
router.include_router(training_goals.router)
router.include_router(health.router)
router.include_router(body_types.router)
router.include_router(timezone.router)
router.include_router(confirmation.router)
router.include_router(navigation.router)

# Экспортировать главный роутер
__all__ = ["router"]
