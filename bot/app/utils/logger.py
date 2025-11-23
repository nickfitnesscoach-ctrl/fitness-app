"""
Настройка логирования для бота.
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

from app.config import settings
from app.utils.secret_filter import apply_secret_filter_to_logger


def setup_logger(name: str = "bot") -> logging.Logger:
    """
    Настраивает логгер для бота.

    Args:
        name: Имя логгера

    Returns:
        Настроенный logger
    """
    logger = logging.getLogger(name)

    # Уровень логирования из конфига
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(log_level)

    # Очистить существующие хендлеры (если есть)
    logger.handlers.clear()

    # Формат логов
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler (всегда включён)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (если указан в конфиге)
    if settings.LOG_FILE:
        # Создать директорию для логов, если её нет
        log_file_path = Path(settings.LOG_FILE)
        log_file_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            filename=settings.LOG_FILE,
            maxBytes=settings.LOG_MAX_BYTES,
            backupCount=settings.LOG_BACKUP_COUNT,
            encoding="utf-8"
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Не распространять логи на родительские логгеры
    logger.propagate = False

    # Применить фильтр для маскирования секретов (API keys, tokens, passwords)
    apply_secret_filter_to_logger(logger)

    # Отключить verbose логирование httpx (может логировать Authorization headers)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Отключить verbose логирование hpack (HTTP/2 headers)
    logging.getLogger("hpack").setLevel(logging.WARNING)

    return logger


# Глобальный экземпляр логгера
logger = setup_logger()
