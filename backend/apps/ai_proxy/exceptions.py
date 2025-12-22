"""
exceptions.py — типы ошибок для AI Proxy.

Простыми словами:
- мы не хотим в коде ловить “голые Exception”
- нам нужны понятные категории ошибок:
  1) Ошибка данных (валидация) — ретраи НЕ нужны
  2) Ошибка доступа (секрет/авторизация) — ретраи НЕ нужны
  3) Таймаут — ретраи нужны
  4) Серверная/сетевая ошибка — ретраи нужны

Эти ошибки используются:
- в apps.ai_proxy.client.AIProxyClient
- в apps.ai.tasks.recognize_food_async (для политики ретраев)
"""


class AIProxyError(Exception):
    """Базовая ошибка AI Proxy (любой тип)."""


class AIProxyValidationError(AIProxyError):
    """
    Ошибка входных данных.
    Пример: неверный формат изображения, пустой файл, неподдерживаемый тип.
    Ретраи бессмысленны.
    """


class AIProxyAuthenticationError(AIProxyError):
    """
    Ошибка доступа.
    Пример: неверный секрет, запрет по правам.
    Ретраи бессмысленны, пока не исправят конфиг/секрет.
    """


class AIProxyTimeoutError(AIProxyError):
    """
    Таймаут запроса к AI Proxy.
    Это временная проблема → ретраи обычно уместны.
    """


class AIProxyServerError(AIProxyError):
    """
    Серверная/сетевая ошибка AI Proxy.
    Пример: 5xx, network error, неожиданный ответ.
    Ретраи уместны.
    """
