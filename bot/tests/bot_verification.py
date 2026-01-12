import pytest
import sys
import os
import time
from unittest.mock import AsyncMock, patch, MagicMock

# Добавляем app в путь
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Переменные окружения должны быть заданы ДО импорта app
os.environ["DJANGO_API_URL"] = "http://backend:8000"
os.environ["TELEGRAM_BOT_TOKEN"] = "123:abc"
os.environ["OPENROUTER_API_KEY"] = "sk-test"
os.environ["TELEGRAM_BOT_API_SECRET"] = "secret"

from app.handlers.survey.confirmation import _perform_save_and_respond
from app.services.backend_api import BackendAPIError

# Шаблон полных данных для FSM
FULL_DATA = {
    "gender": "male",
    "age": 30,
    "height_cm": 180,
    "weight_kg": 80,
    "activity": "moderate",
    "body_now_id": 1,
    "body_now_file": "f1",
    "body_ideal_id": 2,
    "body_ideal_file": "f2",
    "tz": "UTC",
    "utc_offset_minutes": 0,
    "target_weight_kg": 75,
    "ai_created_at": time.time(),
}


@pytest.fixture(autouse=True)
def mock_get_api():
    with patch("app.handlers.survey.confirmation.get_backend_api") as mock:
        api_mock = AsyncMock()
        mock.return_value = api_mock
        yield api_mock


@pytest.mark.asyncio
async def test_perform_save_and_respond_api_failure(mock_get_api):
    """Проверка, что при ошибке API бот отправляет сообщение об ошибке и возвращает False."""
    message_mock = AsyncMock()
    callback_mock = MagicMock()
    callback_mock.message = message_mock
    callback_mock.from_user.id = 12345

    state_mock = AsyncMock()
    state_mock.get_data.return_value = FULL_DATA.copy()

    err = BackendAPIError("Internal Server Error", request_id="req-123")
    err.status_code = 500
    mock_get_api.create_survey.side_effect = err

    result = await _perform_save_and_respond(callback_mock, state_mock, "AI Plan Text", "gpt-4", "v1")

    assert result is False
    message_mock.answer.assert_called()


@pytest.mark.asyncio
async def test_perform_save_and_respond_ttl_expired():
    """Проверка, что если черновик просрочен (TTL), запрос отклоняется."""
    message_mock = AsyncMock()
    callback_mock = MagicMock()
    callback_mock.message = message_mock
    callback_mock.from_user.id = 12345

    state_mock = AsyncMock()
    # Просроченные данные
    expired_data = FULL_DATA.copy()
    expired_data["ai_created_at"] = time.time() - 2400
    state_mock.get_data.return_value = expired_data

    result = await _perform_save_and_respond(callback_mock, state_mock, "AI Plan Text", "gpt-4", "v1")

    assert result is False
    message_mock.answer.assert_called_once()
    assert "Время ожидания истекло" in message_mock.answer.call_args[0][0]
    state_mock.clear.assert_called_once()


@pytest.mark.asyncio
async def test_perform_save_and_respond_non_transient(mock_get_api):
    """Проверка, что при 400 ошибке (non-transient) кнопка Retry не предлагается."""
    message_mock = AsyncMock()
    callback_mock = MagicMock()
    callback_mock.message = message_mock
    callback_mock.from_user.id = 12345

    state_mock = AsyncMock()
    state_mock.get_data.return_value = FULL_DATA.copy()

    err = BackendAPIError("Bad Request", request_id="req-400")
    err.status_code = 400
    mock_get_api.create_survey.side_effect = err

    await _perform_save_and_respond(callback_mock, state_mock, "AI Plan Text", "gpt-4", "v1")

    state_mock.clear.assert_called_once()
    kwargs = message_mock.answer.call_args[1]
    assert "reply_markup" not in kwargs or kwargs["reply_markup"] is None
