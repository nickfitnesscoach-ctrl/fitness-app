"""
Вспомогательные функции для хендлеров опроса.
"""

from aiogram import Bot
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from app.texts.survey import *
from app.keyboards import *
from app.utils.logger import logger


def _plans_word(count: int) -> str:
    """
    Правильное склонение слова 'план'.

    Args:
        count: Количество планов

    Returns:
        'план', 'плана' или 'планов'
    """
    if count % 10 == 1 and count % 100 != 11:
        return "план"
    elif 2 <= count % 10 <= 4 and (count % 100 < 10 or count % 100 >= 20):
        return "плана"
    else:
        return "планов"


async def _safe_delete_message(bot: Bot, chat_id: int, message_id: int, user_id: int = None) -> bool:
    """
    Безопасное удаление сообщения с детальной обработкой ошибок.

    Args:
        bot: Bot instance
        chat_id: ID чата
        message_id: ID сообщения для удаления
        user_id: ID пользователя (для логирования)

    Returns:
        True если сообщение удалено, False если не удалось
    """
    from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        return True
    except TelegramBadRequest as e:
        error_msg = str(e).lower()
        if "message to delete not found" in error_msg or "message can't be deleted" in error_msg:
            logger.debug(f"Message {message_id} already deleted or can't be deleted")
        else:
            logger.warning(f"Failed to delete message {message_id}: {e}")
        return False
    except TelegramForbiddenError:
        logger.error(f"Bot blocked by user {user_id} (chat_id={chat_id})")
        return False
    except Exception as e:
        logger.warning(f"Unexpected error deleting message {message_id}: {e}")
        return False


async def show_confirmation(message: Message, state: FSMContext) -> None:
    """Показывает подтверждение всех введённых данных."""
    from app.texts.survey import ACTIVITY_LABELS

    data = await state.get_data()

    def format_gender(gender: str) -> str:
        return "Мужской" if gender == "male" else "Женский"

    def format_target_weight(weight: float | None) -> str:
        return f"{weight} кг" if weight else "Без изменений"

    def format_utc_offset(minutes: int) -> str:
        hours = minutes // 60
        mins = abs(minutes % 60)
        sign = "+" if hours >= 0 else "-"
        if mins > 0:
            return f"UTC{sign}{abs(hours)}:{mins:02d}"
        return f"UTC{sign}{abs(hours)}"

    def format_training_level(level: str | None) -> str:
        return TRAINING_LEVEL_LABELS.get(level, "не указан")

    def format_body_goals(goals: list[str] | None) -> str:
        if not goals:
            return "не выбраны"
        return ", ".join(BODY_GOALS_LABELS.get(goal, goal) for goal in goals)

    def format_health_limitations(limitations: list[str] | None) -> str:
        if not limitations:
            return "не указаны"
        if "none" in limitations:
            return HEALTH_LIMITATIONS_LABELS.get("none", "нет ограничений")
        return ", ".join(HEALTH_LIMITATIONS_LABELS.get(item, item) for item in limitations)

    # Форматирование данных
    confirmation_text = CONFIRM_DATA_HEADER + CONFIRM_DATA_TEMPLATE.format(
        gender=format_gender(data.get("gender")),
        age=data.get("age"),
        height=data.get("height_cm"),
        weight=data.get("weight_kg"),
        target_weight=format_target_weight(data.get("target_weight_kg")),
        activity=ACTIVITY_LABELS.get(data.get("activity"), data.get("activity")),
        training_level=format_training_level(data.get("training_level")),
        body_goals=format_body_goals(data.get("body_goals")),
        health_limitations=format_health_limitations(data.get("health_limitations")),
        body_now_id=data.get("body_now_id"),
        body_now_label=data.get("body_now_label"),
        body_ideal_id=data.get("body_ideal_id"),
        body_ideal_label=data.get("body_ideal_label"),
        tz=data.get("tz"),
        utc_offset=format_utc_offset(data.get("utc_offset_minutes", 0))
    )

    confirmation_text += "\n" + CONFIRM_QUESTION

    await message.answer(
        confirmation_text,
        reply_markup=get_confirmation_keyboard(),
        parse_mode="HTML",
        disable_notification=True
    )
