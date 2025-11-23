"""
Хендлеры выбора часового пояса в опросе Personal Plan.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.states import SurveyStates
from app.texts.survey import TZ_MANUAL_INPUT, TZ_INVALID
from app.validators import validate_and_normalize_timezone
from app.services.events import log_survey_step_completed
from app.utils.logger import logger
from .helpers import show_confirmation, _safe_delete_message

router = Router(name="survey_timezone")


@router.callback_query(F.data.startswith("tz:"), SurveyStates.TZ)
async def process_tz_button(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора часового пояса через кнопку."""
    parts = callback.data.split(":")
    if len(parts) != 2:
        await callback.answer("❌ Некорректные данные", show_alert=True)
        logger.warning(f"Invalid tz callback_data: {callback.data}")
        return

    tz_value = parts[1]

    if tz_value == "manual":
        # Запросить ручной ввод
        await callback.message.answer(TZ_MANUAL_INPUT, parse_mode="HTML", disable_notification=True)
        await callback.answer()
        return

    # Валидация и нормализация
    result = validate_and_normalize_timezone(tz_value)
    if result is None:
        await callback.answer("❌ Некорректный часовой пояс", show_alert=True)
        return

    iana_tz, offset_minutes = result
    await state.update_data(tz=iana_tz, utc_offset_minutes=offset_minutes)

    user_id = callback.from_user.id
    log_survey_step_completed(user_id, "TZ", {"tz": iana_tz, "offset_minutes": offset_minutes})

    # Переход к подтверждению
    await state.set_state(SurveyStates.CONFIRM)

    # Удаляем старое сообщение и показываем подтверждение
    await callback.message.delete()
    await show_confirmation(callback.message, state)
    await callback.answer()


@router.message(SurveyStates.TZ, F.text)
async def process_tz_manual(message: Message, state: FSMContext):
    """Обработка ручного ввода часового пояса."""
    result = validate_and_normalize_timezone(message.text)

    if result is None:
        # Удалить сообщение пользователя с некорректным вводом
        try:
            await message.delete()
        except Exception:
            pass
        error_msg = await message.answer(TZ_INVALID, parse_mode="HTML", disable_notification=True)
        await state.update_data(last_bot_message_id=error_msg.message_id)
        return

    iana_tz, offset_minutes = result
    await state.update_data(tz=iana_tz, utc_offset_minutes=offset_minutes)

    user_id = message.from_user.id
    log_survey_step_completed(user_id, "TZ", {"tz": iana_tz, "offset_minutes": offset_minutes})

    # Переход к подтверждению
    await state.set_state(SurveyStates.CONFIRM)
    await show_confirmation(message, state)
