"""
HTTP client для взаимодействия с Django Backend API.
Все операции с БД Personal Plan происходят через этот клиент.
"""

import logging
import uuid
from typing import Any, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings

logger = logging.getLogger(__name__)


class BackendAPIError(Exception):
    """Базовое исключение для ошибок Backend API."""

    def __init__(self, message: str, request_id: Optional[str] = None):
        super().__init__(message)
        self.request_id = request_id


class BackendAPIClient:
    """
    Async HTTP клиент для взаимодействия с Django Backend API.

    Использует httpx для async запросов и tenacity для retry логики.
    Все запросы аутентифицируются через X-Bot-Secret header.
    """

    def __init__(self, base_url: Optional[str] = None, timeout: int = 30, secret: Optional[str] = None):
        """
        Инициализация клиента.

        Args:
            base_url: Базовый URL Django API (по умолчанию из settings.DJANGO_API_URL)
            timeout: Таймаут для запросов в секундах
            secret: Секретный ключ для X-Bot-Secret header
        """
        self.base_url = base_url or settings.DJANGO_API_URL
        self.timeout = timeout
        self.secret = secret or getattr(settings, "TELEGRAM_BOT_API_SECRET", None)

        if not self.base_url:
            raise ValueError(
                "DJANGO_API_URL не задан в настройках. "
                "Укажите его в .env файле (например, DJANGO_API_URL=http://backend:8000/api/v1)"
            )

        # Убираем trailing slash для единообразия
        self.base_url = self.base_url.rstrip("/")

        # Предупреждение если секрет не задан
        if not self.secret:
            logger.warning(
                "[BackendAPI] TELEGRAM_BOT_API_SECRET не задан! API вызовы могут быть отклонены в production."
            )

        logger.info(
            "[BackendAPI] Инициализирован клиент: base_url=%s, timeout=%ds, secret=%s",
            self.base_url,
            self.timeout,
            "***" if self.secret else "NOT SET",
        )

    def _get_retry_decorator(self):
        """Создаёт retry декоратор с настройками из settings."""
        return retry(
            stop=stop_after_attempt(settings.DJANGO_RETRY_ATTEMPTS),
            wait=wait_exponential(
                multiplier=settings.DJANGO_RETRY_MULTIPLIER,
                min=settings.DJANGO_RETRY_MIN_WAIT,
                max=settings.DJANGO_RETRY_MAX_WAIT,
            ),
            retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
            reraise=True,
        )

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        json: Optional[dict] = None,
    ) -> dict[str, Any]:
        """
        Выполняет HTTP запрос с retry логикой.

        Args:
            method: HTTP метод (GET, POST, etc.)
            endpoint: Endpoint относительно base_url (например, "/telegram/users/get-or-create/")
            params: Query параметры для GET запросов
            json: JSON данные для POST запросов

        Returns:
            Распарсенный JSON ответ

        Raises:
            BackendAPIError: При ошибках API или сетевых проблемах
        """
        url = f"{self.base_url}{endpoint}"

        try:
            logger.debug("[BackendAPI] %s %s | params=%s | json=%s", method, url, params, json)

            # Локальная функция для выполнения запроса
            @self._get_retry_decorator()
            async def _do_run():
                # Всегда генерируем или используем X-Request-ID для симметрии
                request_id = str(uuid.uuid4())
                headers = {"X-Bot-Secret": self.secret or "", "X-Forwarded-Proto": "https", "X-Request-ID": request_id}
                async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        params=params,
                        json=json,
                        headers=headers,
                    )
                    # Прикрепляем RID к объекту ответа для логов выше
                    response.request_id = request_id
                    return response

            response = await _do_run()
            # Берем RID из ответа (бэк обязан вернуть тот же) или из нашего запроса (fallback)
            request_id = response.headers.get("X-Request-ID") or getattr(response, "request_id", "unknown")

            # Логируем ошибки 4xx и 5xx
            if response.status_code >= 400:
                body_preview = response.text[:2048] if response.text else "No body"
                logger.error(
                    "[BackendAPI] HTTP Error %d: %s | URL: %s | RID: %s | Body: %s",
                    response.status_code,
                    response.reason_phrase,
                    url,
                    request_id,
                    body_preview,
                )

                # Извлекаем детали ошибки
                error_detail = "Unknown error"
                try:
                    error_data = response.json()
                    if isinstance(error_data, dict) and "error" in error_data:
                        err = error_data["error"]
                        if isinstance(err, dict):
                            error_detail = err.get("message") or err.get("code") or str(err)
                        else:
                            error_detail = str(err)
                    else:
                        error_detail = error_data.get("detail") or str(error_data)
                except Exception:
                    error_detail = response.text[:512]

                raise BackendAPIError(f"HTTP {response.status_code}: {error_detail}", request_id=request_id)

            result = response.json()
            logger.debug("[BackendAPI] Успешный ответ. RID: %s | Result: %s", request_id, result)
            return result

        except BackendAPIError:
            raise
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            logger.error("[BackendAPI] Сетевая ошибка при обращении к %s: %s", url, e)
            raise BackendAPIError(f"Не удалось подключиться к Backend API: {e}") from e
        except Exception as e:
            logger.error("[BackendAPI] Неожиданная ошибка: %s", e, exc_info=True)
            raise BackendAPIError(f"Неожиданная ошибка: {e}") from e

    async def get_or_create_user(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        full_name: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Получить или создать пользователя по telegram_id.

        Args:
            telegram_id: Telegram ID пользователя
            username: Telegram username (без @)
            full_name: Полное имя пользователя

        Returns:
            {
                "telegram_id": int,
                "username": str,
                "first_name": str,
                "last_name": str,
                "display_name": str,
                "created": bool  # True если пользователь был создан
            }
        """
        params = {"telegram_id": telegram_id}
        if username:
            params["username"] = username
        if full_name:
            params["full_name"] = full_name

        return await self._request("GET", "/telegram/users/get-or-create/", params=params)

    async def create_survey(
        self,
        telegram_id: int,
        gender: str,
        age: int,
        height_cm: int,
        weight_kg: float,
        activity: str,
        body_now_id: int,
        body_now_file: str,
        body_ideal_id: int,
        body_ideal_file: str,
        timezone: str,
        utc_offset_minutes: int,
        target_weight_kg: Optional[float] = None,
        training_level: Optional[str] = None,
        body_goals: Optional[list[str]] = None,
        health_limitations: Optional[list[str]] = None,
        body_now_label: Optional[str] = None,
        body_ideal_label: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Создать опрос Personal Plan.

        Args:
            telegram_id: Telegram ID пользователя
            gender: Пол ('male' или 'female')
            age: Возраст (14-80)
            height_cm: Рост в см (120-250)
            weight_kg: Вес в кг (30-300)
            activity: Уровень активности ('sedentary', 'light', 'moderate', 'active', 'very_active')
            body_now_id: ID текущего типа телосложения
            body_now_file: Файл изображения текущего тела
            body_ideal_id: ID желаемого типа телосложения
            body_ideal_file: Файл изображения желаемого тела
            timezone: Часовой пояс (например, 'Europe/Moscow')
            utc_offset_minutes: Смещение UTC в минутах
            target_weight_kg: Целевой вес (опционально)
            training_level: Уровень тренированности (опционально)
            body_goals: Цели по телу (опционально)
            health_limitations: Ограничения по здоровью (опционально)
            body_now_label: Метка текущего тела (опционально)
            body_ideal_label: Метка желаемого тела (опционально)

        Returns:
            Данные созданного опроса (PersonalPlanSurvey)
        """
        data = {
            "telegram_id": telegram_id,
            "gender": gender,
            "age": age,
            "height_cm": height_cm,
            "weight_kg": weight_kg,
            "activity": activity,
            "body_now_id": body_now_id,
            "body_now_file": body_now_file,
            "body_ideal_id": body_ideal_id,
            "body_ideal_file": body_ideal_file,
            "timezone": timezone,
            "utc_offset_minutes": utc_offset_minutes,
        }

        # Добавляем опциональные поля
        if target_weight_kg is not None:
            data["target_weight_kg"] = target_weight_kg
        if training_level:
            data["training_level"] = training_level
        if body_goals:
            data["body_goals"] = body_goals
        if health_limitations:
            data["health_limitations"] = health_limitations
        if body_now_label:
            data["body_now_label"] = body_now_label
        if body_ideal_label:
            data["body_ideal_label"] = body_ideal_label

        return await self._request("POST", "/telegram/personal-plan/survey/", json=data)

    async def create_plan(
        self,
        telegram_id: int,
        ai_text: str,
        survey_id: Optional[int] = None,
        ai_model: Optional[str] = None,
        prompt_version: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Создать Personal Plan (AI-генерированный план).

        Args:
            telegram_id: Telegram ID пользователя
            ai_text: Текст сгенерированного AI плана
            survey_id: ID опроса (опционально)
            ai_model: Название AI модели (опционально)
            prompt_version: Версия промпта (опционально)

        Returns:
            Данные созданного плана (PersonalPlan)

        Raises:
            BackendAPIError: Если превышен лимит (3 плана в день) или другие ошибки
        """
        data = {
            "telegram_id": telegram_id,
            "ai_text": ai_text,
        }

        if survey_id is not None:
            data["survey_id"] = survey_id
        if ai_model:
            data["ai_model"] = ai_model
        if prompt_version:
            data["prompt_version"] = prompt_version

        return await self._request("POST", "/telegram/personal-plan/plan/", json=data)

    async def count_plans_today(self, telegram_id: int) -> dict[str, Any]:
        """
        Получить количество планов, созданных сегодня для пользователя.

        Args:
            telegram_id: Telegram ID пользователя

        Returns:
            {
                "count": int,        # Количество планов сегодня
                "limit": int,        # Максимальный лимит в день
                "can_create": bool   # Можно ли создать ещё план
            }
        """
        params = {"telegram_id": telegram_id}
        return await self._request("GET", "/telegram/personal-plan/count-today/", params=params)


# Глобальный экземпляр клиента
_backend_api_client: Optional[BackendAPIClient] = None


def get_backend_api() -> BackendAPIClient:
    """
    Получить глобальный экземпляр BackendAPIClient (singleton).

    Returns:
        Инициализированный BackendAPIClient
    """
    global _backend_api_client
    if _backend_api_client is None:
        _backend_api_client = BackendAPIClient(
            base_url=settings.DJANGO_API_URL,
            timeout=settings.DJANGO_API_TIMEOUT,
        )
    return _backend_api_client
