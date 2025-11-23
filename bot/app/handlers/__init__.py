"""
Регистрация всех хендлеров.
"""

from aiogram import Dispatcher

from app.config import settings
from app.utils.logger import logger


def register_all_handlers(dp: Dispatcher):
    """Регистрирует все хендлеры бота."""

    # Базовые хендлеры (всегда активны)
    # from .common import router as common_router
    # dp.include_router(common_router)

    # Personal Plan (условная регистрация через feature flag)
    if settings.is_personal_plan_enabled:
        from .survey import router as personal_plan_router
        dp.include_router(personal_plan_router)
        logger.info("[OK] Personal Plan feature enabled")
    else:
        logger.warning("[!] Personal Plan feature disabled")
