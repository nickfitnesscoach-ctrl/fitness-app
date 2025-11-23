"""
Фильтр для маскирования секретных данных в логах (API keys, tokens, passwords).

Предотвращает утечку чувствительных данных при DEBUG_MODE=True или verbose logging.
"""

import logging
import re
from typing import Pattern


class SecretMaskingFilter(logging.Filter):
    """
    Logging filter для маскирования секретных данных в log records.

    Маскирует:
    - API keys в формате "Bearer <key>" или "sk-<key>"
    - Telegram bot tokens
    - Database passwords в connection strings
    - Any potential secrets (длинные hex/base64 строки)
    """

    # Паттерны для поиска секретов
    PATTERNS: list[tuple[Pattern[str], str]] = [
        # Bearer tokens (Authorization: Bearer <token>)
        (re.compile(r'Bearer\s+([a-zA-Z0-9_\-\.]{20,})', re.IGNORECASE), r'Bearer ***MASKED***'),

        # API keys в формате sk-<key> (OpenAI/OpenRouter style, включая sk-proj-...)
        (re.compile(r'sk-[a-zA-Z0-9\-]{20,}', re.IGNORECASE), 'sk-***MASKED***'),

        # Telegram bot tokens (формат: 123456:ABC-DEF1234...)
        (re.compile(r'\d{8,10}:[a-zA-Z0-9_\-]{30,}'), '***MASKED_BOT_TOKEN***'),

        # Database passwords в connection strings (postgresql://user:password@host)
        (re.compile(r'(postgresql\+asyncpg://[^:]+:)([^@]+)(@)', re.IGNORECASE), r'\1***MASKED***\3'),
        (re.compile(r'(postgres://[^:]+:)([^@]+)(@)', re.IGNORECASE), r'\1***MASKED***\3'),

        # Generic secrets: длинные hex строки (64+ символов)
        (re.compile(r'\b[a-fA-F0-9]{64,}\b'), '***MASKED_HEX***'),

        # Generic secrets: длинные base64-like строки (40+ символов)
        (re.compile(r'\b[a-zA-Z0-9+/=]{40,}\b'), '***MASKED_B64***'),

        # Authorization headers в логах httpx
        (re.compile(r"'Authorization':\s*'([^']+)'", re.IGNORECASE), r"'Authorization': '***MASKED***'"),
        (re.compile(r'"Authorization":\s*"([^"]+)"', re.IGNORECASE), r'"Authorization": "***MASKED***"'),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Фильтрует log record, маскируя секретные данные.

        Args:
            record: Log record для фильтрации

        Returns:
            True (always) - record всегда проходит, но с замаскированными данными
        """
        # Маскируем секреты в сообщении
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            record.msg = self._mask_secrets(record.msg)

        # Маскируем секреты в args (если есть)
        if hasattr(record, 'args') and record.args:
            if isinstance(record.args, dict):
                record.args = {
                    key: self._mask_secrets(str(value)) if isinstance(value, str) else value
                    for key, value in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    self._mask_secrets(str(arg)) if isinstance(arg, str) else arg
                    for arg in record.args
                )

        return True

    def _mask_secrets(self, text: str) -> str:
        """
        Маскирует все секреты в тексте.

        Args:
            text: Текст для маскирования

        Returns:
            Текст с замаскированными секретами
        """
        for pattern, replacement in self.PATTERNS:
            text = pattern.sub(replacement, text)
        return text


def apply_secret_filter_to_logger(logger: logging.Logger) -> None:
    """
    Применяет SecretMaskingFilter ко всем handlers логгера.

    Args:
        logger: Logger для применения фильтра
    """
    secret_filter = SecretMaskingFilter()

    # Применить к самому логгеру
    logger.addFilter(secret_filter)

    # Применить ко всем существующим handlers
    for handler in logger.handlers:
        handler.addFilter(secret_filter)
