"""
Хендлер выбора уровня активности в опросе Personal Plan.
"""

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from app.states import SurveyStates
from app.texts.survey import TRAINING_LEVEL_QUESTION
from app.keyboards import get_training_level_keyboard
from app.services.events import log_survey_step_completed
from app.utils.logger import logger
from .helpers import _safe_delete_message

router = Router(name="survey_activity")


@router.callback_query(F.data.startswith("activity:"), SurveyStates.ACTIVITY)
async def process_activity(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработка выбора уровня активности."""
    parts = callback.data.split(":")
    if len(parts) != 2:
        await callback.answer("❌ Некорректные данные", show_alert=True)
        logger.warning(f"Invalid activity callback_data: {callback.data}")
        return

    activity = parts[1]
    # Validate activity value against known options
    valid_activities = ["sedentary", "light", "moderate", "active"]
    if activity not in valid_activities:
        await callback.answer("❌ Некорректный уровень активности", show_alert=True)
        logger.warning(f"Invalid activity value: {activity}")
        return

    await state.update_data(activity=activity)

    user_id = callback.from_user.id
    log_survey_step_completed(user_id, "ACTIVITY", {"activity": activity})

    # Переход к следующему шагу - уровень тренированности
    await state.set_state(SurveyStates.TRAINING_LEVEL)

    data = await state.get_data()
    last_msg_id = data.get("last_bot_message_id")
    if last_msg_id:
        await _safe_delete_message(bot, callback.message.chat.id, last_msg_id, user_id)
    try:
        await callback.message.delete()
    except Exception:
        pass

    sent_msg = await callback.message.answer(
        TRAINING_LEVEL_QUESTION,
        reply_markup=get_training_level_keyboard(),
        parse_mode="HTML",
        disable_notification=True,
    )
    await state.update_data(last_bot_message_id=sent_msg.message_id)
    await callback.answer()
