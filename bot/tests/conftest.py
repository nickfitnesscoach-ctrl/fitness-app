"""
Pytest fixtures for testing.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import User, Chat, Message, CallbackQuery


@pytest.fixture
def bot():
    """Mock Bot instance."""
    bot = AsyncMock(spec=Bot)
    bot.id = 123456789
    bot.token = "test_token"
    return bot


@pytest.fixture
def user():
    """Mock User instance."""
    return User(
        id=12345,
        is_bot=False,
        first_name="Test",
        last_name="User",
        username="testuser",
        language_code="en"
    )


@pytest.fixture
def chat():
    """Mock Chat instance."""
    return Chat(
        id=12345,
        type="private"
    )


@pytest.fixture
def message(user, chat):
    """Mock Message instance."""
    msg = MagicMock(spec=Message)
    msg.from_user = user
    msg.chat = chat
    msg.message_id = 1
    msg.text = "test"
    msg.bot = AsyncMock(spec=Bot)
    msg.answer = AsyncMock()
    msg.delete = AsyncMock()
    return msg


@pytest.fixture
def callback_query(user, message):
    """Mock CallbackQuery instance."""
    callback = MagicMock(spec=CallbackQuery)
    callback.from_user = user
    callback.message = message
    callback.data = "test:data"
    callback.answer = AsyncMock()
    return callback


@pytest.fixture
def storage():
    """FSM storage."""
    return MemoryStorage()


@pytest.fixture
def state(storage, bot, user, chat):
    """Mock FSMContext instance."""
    from aiogram.fsm.storage.base import StorageKey
    return FSMContext(
        storage=storage,
        key=StorageKey(bot_id=bot.id, user_id=user.id, chat_id=chat.id)
    )
