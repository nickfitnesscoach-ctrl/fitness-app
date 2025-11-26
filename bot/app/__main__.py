"""Точка входа приложения."""

import asyncio
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramConflictError
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import settings
from app.handlers import register_all_handlers
from app.utils.logger import logger


async def on_startup():
    """Действия при запуске бота."""
    logger.info("[START] Starting bot...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG_MODE}")
    logger.info(f"Personal Plan feature: {'ENABLED' if settings.is_personal_plan_enabled else 'DISABLED'}")

    # Проверка наличия изображений body types
    from app.constants import BODY_COUNTS
    from app.utils.paths import validate_image_file_exists

    missing_images = []
    for gender in ["male", "female"]:
        for stage in ["now", "ideal"]:
            count = BODY_COUNTS[gender][stage]
            for variant_id in range(1, count + 1):
                if not validate_image_file_exists(gender, stage, variant_id):
                    missing_images.append(f"{gender}/{stage}/{variant_id}")

    if missing_images:
        logger.warning(f"[WARN] Missing body type images: {missing_images}")
    else:
        logger.info("[OK] All body type images found")


async def on_shutdown():
    """Действия при остановке бота."""
    logger.info("[STOP] Shutting down bot...")
    # Database connection is no longer used - bot communicates via Backend API
    logger.info("[OK] Bot shutdown complete")


async def main():
    """Основная функция запуска бота."""

    # Создать бота
    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML
        )
    )

    # Создать диспетчер с MemoryStorage (для локальной разработки)
    # В production используйте Redis storage
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Зарегистрировать хендлеры
    register_all_handlers(dp)

    # Зарегистрировать startup/shutdown хуки
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Убедиться, что webhook отключен и ожидающие обновления очищены перед polling
    await bot.delete_webhook(drop_pending_updates=True)

    # Запустить polling c обработкой конфликтов параллельных инстансов
    try:
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            logger.info(f"[OK] Bot started successfully! Polling attempt {attempt}/{max_attempts}")
            try:
                await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
            except TelegramConflictError as conflict_error:
                logger.error(
                    "[CONFLICT] Another getUpdates session is running. "
                    "Ensure only one bot instance is active. Error: %s",
                    conflict_error,
                )
                if attempt == max_attempts:
                    raise
                await asyncio.sleep(5)
                continue
            break
    except KeyboardInterrupt:
        logger.info("[PAUSE] Bot stopped by user")
    except Exception as e:
        logger.error(f"[ERROR] Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("[BYE] Goodbye!")
