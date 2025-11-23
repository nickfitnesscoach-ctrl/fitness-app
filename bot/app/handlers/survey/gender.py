"""
Хендлер выбора пола в опросе Personal Plan.
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from app.states import SurveyStates
from app.texts.survey import AGE_QUESTION
from app.keyboards import get_empty_keyboard
from app.services.events import log_survey_step_completed
from app.utils.logger import logger

router = Router(name="survey_gender")


@router.callback_query(F.data.startswith("gender:"), SurveyStates.GENDER)
async def process_gender(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора пола."""
    parts = callback.data.split(":")
    if len(parts) != 2 or parts[1] not in ["male", "female"]:
        await callback.answer("❌ Некорректные данные", show_alert=True)
        logger.warning(f"Invalid gender callback_data: {callback.data}")
        return

    gender = parts[1]
    await state.update_data(gender=gender)

    user_id = callback.from_user.id
    log_survey_step_completed(user_id, "GENDER", {"gender": gender})

    # Переход к следующему шагу
    await state.set_state(SurveyStates.AGE)

    # Удаляем старое сообщение и отправляем новое (чтобы его можно было удалить позже)
    await callback.message.delete()
    sent_msg = await callback.message.answer(
        AGE_QUESTION,
        reply_markup=get_empty_keyboard(),
        parse_mode="HTML",
        disable_notification=True
    )
    await state.update_data(last_bot_message_id=sent_msg.message_id)
    await callback.answer()
