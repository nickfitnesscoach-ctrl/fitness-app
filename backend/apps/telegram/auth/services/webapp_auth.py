"""
Единый сервис проверки Telegram WebApp initData.

Зачем нужен:
- Telegram Mini App присылает initData (query-string), подписанный Telegram.
- Мы обязаны проверить подпись (hash), иначе любой может "подделать" пользователя.
- Этот сервис используется в нескольких местах (auth backend / views / middleware),
  поэтому логика должна быть ОДНА и одинаковая везде.

Что мы делаем:
1) Парсим initData как query-string
2) Проверяем что есть hash
3) Проверяем TTL по auth_date (не старое и не "из будущего")
4) Собираем data_check_string (ключ=значение, сортировка)
5) Считаем HMAC по формуле Telegram и сравниваем с hash
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import logging
import time
from typing import Dict, Optional, Tuple
from urllib.parse import parse_qsl

from django.conf import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Настройки безопасности (дефолты)
# ---------------------------------------------------------------------

DEFAULT_MAX_AGE_SECONDS = 60 * 60 * 24  # 24 часа
MAX_INIT_DATA_LENGTH = 10_000  # защита от мусорных огромных заголовков/тела


@dataclass(frozen=True)
class ValidationResult:
    """
    Результат успешной валидации.

    parsed — данные initData БЕЗ поля hash.
    auth_date — когда Telegram выдал подпись (unix timestamp).
    """
    parsed: Dict[str, str]
    auth_date: int


class TelegramWebAppAuthService:
    """Сервис проверки подписи Telegram WebApp initData."""

    def __init__(self, bot_token: str):
        self._bot_token = bot_token

    @property
    def bot_token(self) -> str:
        return self._bot_token

    def validate_init_data(
        self,
        raw_init_data: str,
        *,
        max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
    ) -> Optional[Dict[str, str]]:
        """
        Главная функция:
        - возвращает parsed_data (без hash) если всё ок
        - иначе возвращает None

        max_age_seconds:
        - ограничивает "срок годности" подписи
        - в проде обычно 1-24 часа норм
        """
        result = self.validate_init_data_detailed(raw_init_data, max_age_seconds=max_age_seconds)
        return result.parsed if result else None

    def validate_init_data_detailed(
        self,
        raw_init_data: str,
        *,
        max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
    ) -> Optional[ValidationResult]:
        """
        То же самое, но возвращает расширенный результат (в т.ч. auth_date).
        Удобно для логики, где важен timestamp.
        """
        if not raw_init_data:
            return None

        if not self._bot_token:
            # Это ошибка конфигурации. В проде так быть не должно.
            logger.error("[WebAppAuth] TELEGRAM_BOT_TOKEN is missing")
            return None

        # Простейшая защита от DoS: слишком длинные строки не обрабатываем
        if len(raw_init_data) > MAX_INIT_DATA_LENGTH:
            logger.warning("[WebAppAuth] initData too long")
            return None

        try:
            parsed, received_hash = self._parse_init_data(raw_init_data)
            if not received_hash:
                return None

            auth_date = self._extract_auth_date(parsed)
            if auth_date is None:
                return None

            if not self._check_ttl(auth_date, max_age_seconds=max_age_seconds):
                return None

            data_check_string = self._build_data_check_string(parsed)
            calculated_hash = self._calculate_hash(data_check_string)

            if not hmac.compare_digest(calculated_hash, received_hash):
                # Не пишем calculated/received в лог (это лишнее)
                logger.warning("[WebAppAuth] Hash mismatch")
                return None

            return ValidationResult(parsed=parsed, auth_date=auth_date)

        except Exception:
            # В логи пишем stacktrace, клиенту наружу это не уходит
            logger.exception("[WebAppAuth] Validation error")
            return None

    # -----------------------------------------------------------------
    # Внутренние шаги
    # -----------------------------------------------------------------

    def _parse_init_data(self, raw_init_data: str) -> Tuple[Dict[str, str], Optional[str]]:
        """
        Парсим query-string initData.
        Возвращаем:
          parsed_data без hash
          received_hash
        """
        parsed_data = dict(parse_qsl(raw_init_data, keep_blank_values=True))
        received_hash = parsed_data.pop("hash", None)

        if not received_hash:
            logger.warning("[WebAppAuth] No hash in initData")
            return {}, None

        return parsed_data, received_hash

    def _extract_auth_date(self, parsed_data: Dict[str, str]) -> Optional[int]:
        """
        auth_date — unix timestamp, обязательное поле по стандарту Telegram.
        """
        raw = parsed_data.get("auth_date")
        if not raw:
            logger.warning("[WebAppAuth] No auth_date in initData")
            return None

        try:
            auth_date = int(raw)
        except (ValueError, TypeError):
            logger.warning("[WebAppAuth] Invalid auth_date format")
            return None

        return auth_date

    def _check_ttl(self, auth_date: int, *, max_age_seconds: int) -> bool:
        """
        Проверяем "свежесть" подписи.

        Дополнительно:
        - защита от auth_date "из будущего" (например, если кто-то подделывает данные)
        """
        if max_age_seconds <= 0:
            return True

        now = int(time.time())

        # auth_date из будущего > 60 сек — подозрительно
        if auth_date > now + 60:
            logger.warning("[WebAppAuth] auth_date is in the future")
            return False

        age = now - auth_date
        if age > max_age_seconds:
            logger.warning("[WebAppAuth] initData expired")
            return False

        return True

    def _build_data_check_string(self, parsed_data: Dict[str, str]) -> str:
        """
        Собираем data_check_string:
        - ключ=значение
        - сортировка по ключам
        - разделитель — \n
        """
        # Важно: hash уже удалён до этого
        return "\n".join(f"{k}={v}" for k, v in sorted(parsed_data.items()))

    def _calculate_hash(self, data_check_string: str) -> str:
        """
        Формула Telegram (WebAppData):
        secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)
        hash = HMAC_SHA256(key=secret_key, msg=data_check_string).hexdigest()
        """
        secret_key = hmac.new(
            key=b"WebAppData",
            msg=self._bot_token.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()

        return hmac.new(
            key=secret_key,
            msg=data_check_string.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()

    # -----------------------------------------------------------------
    # Извлечение user
    # -----------------------------------------------------------------

    def get_user_data_from_init_data(self, parsed_data: Dict[str, str]) -> Optional[dict]:
        """
        Достаём JSON из поля 'user' и парсим.
        """
        user_json = parsed_data.get("user")
        if not user_json:
            return None

        try:
            return json.loads(user_json)
        except json.JSONDecodeError:
            logger.warning("[WebAppAuth] Invalid user JSON")
            return None

    def get_user_id_from_init_data(self, parsed_data: Dict[str, str]) -> Optional[int]:
        """
        Достаём user.id (telegram_id) из parsed_data.
        """
        user_data = self.get_user_data_from_init_data(parsed_data)
        if not user_data:
            return None

        try:
            return int(user_data.get("id"))
        except (TypeError, ValueError):
            return None


# ---------------------------------------------------------------------
# Singleton (аккуратно)
# ---------------------------------------------------------------------

_auth_service: Optional[TelegramWebAppAuthService] = None
_auth_service_token: Optional[str] = None


def get_webapp_auth_service() -> TelegramWebAppAuthService:
    """
    Singleton:
    - создаём сервис один раз
    - если TELEGRAM_BOT_TOKEN изменился (например в тестах или при reload),
      пересоздаём сервис
    """
    global _auth_service, _auth_service_token

    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "") or ""

    if _auth_service is None or _auth_service_token != token:
        _auth_service = TelegramWebAppAuthService(token)
        _auth_service_token = token

    return _auth_service
