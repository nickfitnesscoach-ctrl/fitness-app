"""
OpenRouter API клиент для генерации персональных планов.
"""

import httpx
from typing import Dict, Any, Optional
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    retry_if_exception,
    before_sleep_log,
    RetryError
)

from app.config import settings
from app.prompts.personal_plan import get_system_prompt, build_user_message, get_prompt_version
from app.utils.logger import logger


def _is_retryable_http_error(exception: Exception) -> bool:
    """
    Определяет, стоит ли делать retry для данного исключения.

    Args:
        exception: Исключение для проверки

    Returns:
        True если это временная ошибка (429, 503, 502, 504), False иначе
    """
    if not isinstance(exception, httpx.HTTPStatusError):
        return False

    # Retry только на временных ошибках
    retryable_codes = {
        429,  # Too Many Requests (rate limit)
        502,  # Bad Gateway
        503,  # Service Unavailable
        504,  # Gateway Timeout
    }

    return exception.response.status_code in retryable_codes


class OpenRouterClient:
    """Клиент для работы с OpenRouter API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None
    ):
        """
        Инициализация клиента.

        Args:
            base_url: Base URL OpenRouter API
            api_key: API ключ
            model: Название модели
            timeout: Таймаут запроса в секундах
        """
        self.base_url = base_url or settings.OPENROUTER_BASE_URL
        self.api_key = api_key or settings.OPENROUTER_API_KEY
        self.model = model or settings.OPENROUTER_MODEL
        self.timeout = timeout or settings.OPENROUTER_TIMEOUT

    @retry(
        stop=stop_after_attempt(settings.OPENROUTER_RETRY_ATTEMPTS),
        wait=wait_exponential(
            multiplier=settings.OPENROUTER_RETRY_MULTIPLIER,
            min=settings.OPENROUTER_RETRY_MIN_WAIT,
            max=settings.OPENROUTER_RETRY_MAX_WAIT
        ),
        retry=retry_if_exception_type(httpx.HTTPStatusError) & retry_if_exception(_is_retryable_http_error),
        before_sleep=before_sleep_log(logger, log_level="WARNING"),
        reraise=True
    )
    async def _make_api_request(
        self,
        system_prompt: str,
        user_message: str
    ) -> Dict[str, Any]:
        """
        Делает HTTP запрос к OpenRouter API с автоматическим retry.

        Args:
            system_prompt: Системный промпт для AI
            user_message: Сообщение пользователя

        Returns:
            JSON ответ от API

        Raises:
            httpx.HTTPStatusError: При HTTP ошибках (после всех retry попыток)
            httpx.TimeoutException: При таймауте запроса
        """
        # Раздельные таймауты: быстрое подключение, долгое чтение ответа
        timeout_config = httpx.Timeout(
            connect=5.0,  # Быстрое определение недоступности API
            read=self.timeout,  # Достаточно времени для генерации AI
            write=5.0,
            pool=5.0
        )
        async with httpx.AsyncClient(timeout=timeout_config) as client:
            response = await client.post(
                url=f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": settings.PROJECT_URL,  # Для аналитики OpenRouter
                    "X-Title": "AI Lead Magnet Bot",
                    "X-Origin": settings.PROJECT_URL  # Origin для CORS и аналитики
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 2000
                }
            )

            response.raise_for_status()
            return response.json()

    async def generate_plan(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Генерирует персональный план через OpenRouter API.

        Args:
            payload: Данные опроса пользователя

        Returns:
            Словарь с результатом:
            {
                "success": bool,
                "text": str,  # Текст плана от ИИ
                "model": str,  # Использованная модель
                "prompt_version": str,  # Версия промпта
                "error": str | None  # Сообщение об ошибке
            }
        """
        system_prompt = get_system_prompt()
        user_message = build_user_message(payload)

        try:
            # Вызов метода с автоматическим retry
            data = await self._make_api_request(system_prompt, user_message)

            # Извлечь текст ответа
            ai_text = data["choices"][0]["message"]["content"]

            logger.info(f"AI plan generated successfully. Model: {self.model}, Length: {len(ai_text)}")

            return {
                "success": True,
                "text": ai_text,
                "model": self.model,
                "prompt_version": get_prompt_version(),
                "error": None
            }

        except RetryError as e:
            # Все retry попытки исчерпаны
            original_exception = e.last_attempt.exception()
            if isinstance(original_exception, httpx.HTTPStatusError):
                error_msg = f"HTTP error {original_exception.response.status_code} (after {settings.OPENROUTER_RETRY_ATTEMPTS} retries): {original_exception.response.text}"
                logger.error(f"OpenRouter API HTTP error after retries: {error_msg}")
            else:
                error_msg = f"Request failed after {settings.OPENROUTER_RETRY_ATTEMPTS} retries: {str(original_exception)}"
                logger.error(f"OpenRouter API retry exhausted: {error_msg}")

            return {
                "success": False,
                "text": "",
                "model": self.model,
                "prompt_version": get_prompt_version(),
                "error": error_msg
            }

        except httpx.HTTPStatusError as e:
            # Не-retryable HTTP ошибки (4xx кроме 429)
            error_msg = f"HTTP error {e.response.status_code}: {e.response.text}"
            logger.error(f"OpenRouter API HTTP error (non-retryable): {error_msg}")
            return {
                "success": False,
                "text": "",
                "model": self.model,
                "prompt_version": get_prompt_version(),
                "error": error_msg
            }

        except httpx.TimeoutException as e:
            error_msg = f"Request timeout after {self.timeout}s"
            logger.error(f"OpenRouter API timeout: {error_msg}")
            return {
                "success": False,
                "text": "",
                "model": self.model,
                "prompt_version": get_prompt_version(),
                "error": error_msg
            }

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(f"OpenRouter API unexpected error: {error_msg}", exc_info=True)
            return {
                "success": False,
                "text": "",
                "model": self.model,
                "prompt_version": get_prompt_version(),
                "error": error_msg
            }


# Глобальный экземпляр клиента
openrouter_client = OpenRouterClient()
