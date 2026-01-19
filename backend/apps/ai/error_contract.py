"""
Error Contract — единый формат ошибок AI-обработки для EatFit24.

Принципы:
1. Стабильный контракт: error_code + user_title + user_message + user_actions + retry_after_sec
2. Понятен пользователю, удобен фронту, даёт аналитику
3. Разделение Debug/Prod: в prod только user_* + trace_id
4. Backward compatible: старые клиенты продолжают работать

Структура ошибки:
{
    "error_code": "AI_TIMEOUT",
    "user_title": "Не получилось обработать фото",
    "user_message": "Сервис временно недоступен. Попробуйте позже.",
    "user_actions": ["retry", "contact_support"],
    "trace_id": "abc123",
    "retry_after_sec": 30,
    "debug_details": {...}  # Только в DEBUG режиме
}

Использование:
    from apps.ai.error_contract import AIErrorRegistry

    # В коде:
    error = AIErrorRegistry.AI_TIMEOUT
    response_data = error.to_dict(trace_id="abc123")

    # Результат:
    {
        "error_code": "AI_TIMEOUT",
        "user_title": "Не получилось обработать фото",
        "user_message": "Сервер не ответил вовремя. Попробуйте ещё раз.",
        "user_actions": ["retry"],
        "trace_id": "abc123",
        "retry_after_sec": 30
    }
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from django.conf import settings


@dataclass(frozen=True)
class AIErrorDefinition:
    """
    Определение ошибки AI-обработки.

    Fields:
        code: Уникальный код ошибки (UPPERCASE_SNAKE_CASE)
        user_title: Короткий заголовок для пользователя (1-5 слов)
        user_message: Подробное сообщение для пользователя (1-2 предложения)
        user_actions: Список допустимых действий пользователя
        allow_retry: Разрешить ли повторную попытку
        retry_after_sec: Рекомендуемая задержка перед retry (секунды)
        category: Категория ошибки (для аналитики и группировки)
    """

    code: str
    user_title: str
    user_message: str
    user_actions: List[str]  # ["retry", "retake", "contact_support", "upgrade"]
    allow_retry: bool
    retry_after_sec: Optional[int] = None
    category: str = "unknown"  # "timeout", "validation", "limit", "server", "unknown"

    def to_dict(
        self,
        trace_id: Optional[str] = None,
        debug_details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Преобразовать ошибку в словарь для API response.

        Args:
            trace_id: ID трейса для корреляции логов
            debug_details: Технические детали (только в DEBUG режиме)

        Returns:
            Словарь с полями ошибки (готов для JSON serialization)
        """
        result: Dict[str, Any] = {
            "error_code": self.code,
            "user_title": self.user_title,
            "user_message": self.user_message,
            "user_actions": self.user_actions,
            "allow_retry": self.allow_retry,
        }

        if self.retry_after_sec is not None:
            result["retry_after_sec"] = self.retry_after_sec

        if trace_id:
            result["trace_id"] = trace_id

        # Debug details только в DEBUG режиме
        if settings.DEBUG and debug_details:
            result["debug_details"] = debug_details

        return result


# ============================================================================
# Error Registry — централизованный реестр всех ошибок AI
# ============================================================================


class AIErrorRegistry:
    """
    Реестр всех возможных ошибок AI-обработки.

    Все error_code определены здесь, чтобы избежать дублирования и опечаток.
    """

    # ========================================================================
    # Timeout Errors (категория: timeout)
    # ========================================================================

    AI_TIMEOUT = AIErrorDefinition(
        code="AI_TIMEOUT",
        user_title="Не получилось обработать фото",
        user_message="Сервер не ответил вовремя. Попробуйте ещё раз.",
        user_actions=["retry"],
        allow_retry=True,
        retry_after_sec=30,
        category="timeout",
    )

    UPSTREAM_TIMEOUT = AIErrorDefinition(
        code="UPSTREAM_TIMEOUT",
        user_title="Не получилось обработать фото",
        user_message="Сервис распознавания не ответил вовремя. Попробуйте ещё раз.",
        user_actions=["retry"],
        allow_retry=True,
        retry_after_sec=30,
        category="timeout",
    )

    # ========================================================================
    # Server Errors (категория: server)
    # ========================================================================

    AI_SERVER_ERROR = AIErrorDefinition(
        code="AI_SERVER_ERROR",
        user_title="Не получилось обработать фото",
        user_message="Сервер временно недоступен. Попробуйте ещё раз.",
        user_actions=["retry", "contact_support"],
        allow_retry=True,
        retry_after_sec=60,
        category="server",
    )

    UPSTREAM_ERROR = AIErrorDefinition(
        code="UPSTREAM_ERROR",
        user_title="Не получилось обработать фото",
        user_message="Сервис распознавания временно недоступен.",
        user_actions=["retry", "contact_support"],
        allow_retry=True,
        retry_after_sec=60,
        category="server",
    )

    INTERNAL_ERROR = AIErrorDefinition(
        code="INTERNAL_ERROR",
        user_title="Не получилось обработать фото",
        user_message="Внутренняя ошибка сервера. Попробуйте позже.",
        user_actions=["retry", "contact_support"],
        allow_retry=True,
        retry_after_sec=120,
        category="server",
    )

    # ========================================================================
    # Image Validation Errors (категория: validation)
    # ========================================================================

    UNSUPPORTED_IMAGE_FORMAT = AIErrorDefinition(
        code="UNSUPPORTED_IMAGE_FORMAT",
        user_title="Неподдерживаемый формат",
        user_message="Не удалось обработать фото. Отправь как JPEG или сделай скриншот.",
        user_actions=["retake"],
        allow_retry=False,
        category="validation",
    )

    IMAGE_DECODE_FAILED = AIErrorDefinition(
        code="IMAGE_DECODE_FAILED",
        user_title="Не удалось обработать фото",
        user_message="Файл повреждён или не является изображением. Попробуйте другое фото.",
        user_actions=["retake"],
        allow_retry=False,
        category="validation",
    )

    INVALID_IMAGE = AIErrorDefinition(
        code="INVALID_IMAGE",
        user_title="Не удалось обработать фото",
        user_message="Файл повреждён или не является изображением.",
        user_actions=["retake"],
        allow_retry=False,
        category="validation",
    )

    IMAGE_TOO_LARGE = AIErrorDefinition(
        code="IMAGE_TOO_LARGE",
        user_title="Фото слишком большое",
        user_message="Попробуйте сделать другое фото или уменьшить размер.",
        user_actions=["retake"],
        allow_retry=False,
        category="validation",
    )

    UNSUPPORTED_IMAGE_TYPE = AIErrorDefinition(
        code="UNSUPPORTED_IMAGE_TYPE",
        user_title="Неподдерживаемый формат",
        user_message="Пожалуйста, загрузите изображение в формате JPEG, PNG или WEBP.",
        user_actions=["retake"],
        allow_retry=False,
        category="validation",
    )

    # ========================================================================
    # Recognition Errors (категория: validation)
    # ========================================================================

    EMPTY_RESULT = AIErrorDefinition(
        code="EMPTY_RESULT",
        user_title="Не удалось распознать еду",
        user_message="Мы не смогли распознать еду на фото. Попробуйте сделать фото крупнее.",
        user_actions=["retake"],
        allow_retry=False,
        category="validation",
    )

    LOW_CONFIDENCE = AIErrorDefinition(
        code="LOW_CONFIDENCE",
        user_title="Не уверены в результате",
        user_message="Выберите блюдо вручную или сделайте фото ближе при хорошем освещении.",
        user_actions=["manual_select", "retake"],
        allow_retry=False,
        category="validation",
    )

    UNSUPPORTED_CONTENT = AIErrorDefinition(
        code="UNSUPPORTED_CONTENT",
        user_title="Не удалось распознать еду",
        user_message="На фото нет еды или изображение неподходящее. Попробуйте другое фото.",
        user_actions=["retake"],
        allow_retry=False,
        category="validation",
    )

    # ========================================================================
    # Rate Limiting (категория: limit)
    # ========================================================================

    DAILY_PHOTO_LIMIT_EXCEEDED = AIErrorDefinition(
        code="DAILY_PHOTO_LIMIT_EXCEEDED",
        user_title="Дневной лимит исчерпан",
        user_message="Вы исчерпали дневной лимит фото. Оформите PRO для безлимита.",
        user_actions=["upgrade"],
        allow_retry=False,
        category="limit",
    )

    RATE_LIMIT = AIErrorDefinition(
        code="RATE_LIMIT",
        user_title="Слишком много запросов",
        user_message="Подождите немного перед следующей попыткой.",
        user_actions=["retry"],
        allow_retry=True,
        retry_after_sec=60,
        category="limit",
    )

    # ========================================================================
    # System Errors (категория: unknown)
    # ========================================================================

    CANCELLED = AIErrorDefinition(
        code="CANCELLED",
        user_title="Отменено",
        user_message="Обработка была отменена пользователем.",
        user_actions=[],
        allow_retry=True,
        category="unknown",
    )

    PHOTO_NOT_FOUND = AIErrorDefinition(
        code="PHOTO_NOT_FOUND",
        user_title="Фото не найдено",
        user_message="Фото не найдено или недоступно.",
        user_actions=["contact_support"],
        allow_retry=False,
        category="validation",
    )

    INVALID_STATUS = AIErrorDefinition(
        code="INVALID_STATUS",
        user_title="Недопустимое состояние",
        user_message="Можно повторить только неудавшиеся фото.",
        user_actions=["contact_support"],
        allow_retry=False,
        category="validation",
    )

    UNKNOWN_ERROR = AIErrorDefinition(
        code="UNKNOWN_ERROR",
        user_title="Произошла ошибка",
        user_message="Произошла неизвестная ошибка. Попробуйте позже.",
        user_actions=["retry", "contact_support"],
        allow_retry=True,
        retry_after_sec=60,
        category="unknown",
    )

    # ========================================================================
    # Fallback для старых кодов
    # ========================================================================

    @classmethod
    def get_by_code(cls, code: str) -> AIErrorDefinition:
        """
        Получить определение ошибки по коду.

        Args:
            code: Код ошибки (UPPERCASE_SNAKE_CASE)

        Returns:
            AIErrorDefinition для указанного кода или UNKNOWN_ERROR если не найден
        """
        # Пытаемся получить атрибут класса по имени
        error_def = getattr(cls, code, None)
        if error_def and isinstance(error_def, AIErrorDefinition):
            return error_def

        # Fallback: если код не найден, возвращаем UNKNOWN_ERROR
        return cls.UNKNOWN_ERROR

    @classmethod
    def get_all_codes(cls) -> List[str]:
        """
        Получить список всех доступных error_code.

        Returns:
            Список строк с кодами ошибок
        """
        codes = []
        for attr_name in dir(cls):
            if attr_name.startswith("_"):
                continue
            attr = getattr(cls, attr_name)
            if isinstance(attr, AIErrorDefinition):
                codes.append(attr.code)
        return sorted(codes)


# ============================================================================
# Backward Compatibility — маппинг старых кодов на новые
# ============================================================================

# Маппинг старых error_code на новые AIErrorDefinition
LEGACY_ERROR_CODE_MAP: Dict[str, AIErrorDefinition] = {
    # Старые коды из ai_proxy/service.py
    "IMAGE_PROCESSING_ERROR": AIErrorRegistry.IMAGE_DECODE_FAILED,
    "IMAGE_VALIDATION_FAILED": AIErrorRegistry.INVALID_IMAGE,
    # Старые коды из tasks.py
    "AI_ERROR": AIErrorRegistry.AI_SERVER_ERROR,
    "OWNERSHIP_MISMATCH": AIErrorRegistry.UNKNOWN_ERROR,
    "MEAL_NOT_FOUND": AIErrorRegistry.UNKNOWN_ERROR,
    # Для дедупликации с фронтендом
    "PREPROCESS_DECODE_FAILED": AIErrorRegistry.IMAGE_DECODE_FAILED,
    "PREPROCESS_INVALID_IMAGE": AIErrorRegistry.INVALID_IMAGE,
    "PREPROCESS_TIMEOUT": AIErrorRegistry.AI_TIMEOUT,
    "UPSTREAM_INVALID_RESPONSE": AIErrorRegistry.UPSTREAM_ERROR,
    # AI Server controlled errors (from meta.error_code)
    "BLURRY": AIErrorRegistry.UNSUPPORTED_CONTENT,  # Blurry image → retake
    # Legacy test errors (deprecated, kept for backward compat)
    "INVALID_DATE_FORMAT": AIErrorRegistry.UNKNOWN_ERROR,  # Date validation moved to serializer
}


def normalize_error_code(code: str) -> AIErrorDefinition:
    """
    Нормализовать старый error_code в новый AIErrorDefinition.

    Args:
        code: Код ошибки (может быть старый или новый)

    Returns:
        AIErrorDefinition для указанного кода
    """
    # Проверяем legacy map
    if code in LEGACY_ERROR_CODE_MAP:
        return LEGACY_ERROR_CODE_MAP[code]

    # Проверяем registry
    return AIErrorRegistry.get_by_code(code)
