"""
Хендлеры выбора типов фигуры в опросе Personal Plan.
Включает: текущий и идеальный тип фигуры.
"""

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from app.states import SurveyStates
from app.texts.survey import (
    BODY_NOW_SELECTED, BODY_IDEAL_QUESTION_HEADER,
    BODY_IDEAL_SELECTED, TZ_QUESTION
)
from app.keyboards import get_timezone_keyboard
from app.constants import BODY_LABELS
from app.services.image_sender import image_sender
from app.services.events import log_survey_step_completed
from app.utils.logger import logger

router = Router(name="survey_body_types")


# =============================================================================
# ТЕКУЩИЙ ТИП ФИГУРЫ
# =============================================================================

@router.callback_query(F.data.startswith("body:"), SurveyStates.BODY_NOW)
async def process_body_now(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработка выбора текущего типа фигуры."""
    parts = callback.data.split(":")
    if len(parts) != 2:
        await callback.answer("❌ Некорректные данные", show_alert=True)
        logger.warning(f"Invalid body_now callback_data: {callback.data}")
        return

    try:
        variant_id = int(parts[1])
    except ValueError:
        await callback.answer("❌ Некорректный ID варианта", show_alert=True)
        logger.warning(f"Invalid body_now variant_id: {parts[1]}")
        return

    data = await state.get_data()
    gender = data.get("gender", "female")

    # Получить label и file path
    label = BODY_LABELS.get(gender, {}).get("now", {}).get(variant_id, "")
    file_path = f"assets/body_types/{gender}/now/{gender}_now_{variant_id}.jpg"

    await state.update_data(
        body_now_id=variant_id,
        body_now_label=label,
        body_now_file=file_path
    )

    user_id = callback.from_user.id
    log_survey_step_completed(user_id, "BODY_NOW", {"body_now_id": variant_id})

    # Удалить все сообщения с вариантами
    message_ids = data.get("body_now_message_ids", [])
    await image_sender.delete_messages(bot, callback.message.chat.id, message_ids)

    # Переход к следующему шагу - BODY_IDEAL
    await state.set_state(SurveyStates.BODY_IDEAL)

    # Объединяем подтверждение и заголовок следующего шага
    combined_header = BODY_NOW_SELECTED.format(variant_id=variant_id, label=label) + "\n\n" + BODY_IDEAL_QUESTION_HEADER

    # Отправить изображения идеальных типов фигуры
    message_ids = await image_sender.send_body_type_options(
        bot=bot,
        chat_id=callback.message.chat.id,
        gender=gender,
        stage="ideal",
        header_message=combined_header
    )

    await state.update_data(body_ideal_message_ids=message_ids)
    await callback.answer()


# =============================================================================
# ИДЕАЛЬНЫЙ ТИП ФИГУРЫ
# =============================================================================

@router.callback_query(F.data.startswith("body:"), SurveyStates.BODY_IDEAL)
async def process_body_ideal(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработка выбора идеального типа фигуры."""
    parts = callback.data.split(":")
    if len(parts) != 2:
        await callback.answer("❌ Некорректные данные", show_alert=True)
        logger.warning(f"Invalid body_ideal callback_data: {callback.data}")
        return

    try:
        variant_id = int(parts[1])
    except ValueError:
        await callback.answer("❌ Некорректный ID варианта", show_alert=True)
        logger.warning(f"Invalid body_ideal variant_id: {parts[1]}")
        return

    data = await state.get_data()
    gender = data.get("gender", "female")

    # Получить label и file path
    label = BODY_LABELS.get(gender, {}).get("ideal", {}).get(variant_id, "")
    file_path = f"assets/body_types/{gender}/ideal/{gender}_ideal_{variant_id}.jpg"

    await state.update_data(
        body_ideal_id=variant_id,
        body_ideal_label=label,
        body_ideal_file=file_path
    )

    user_id = callback.from_user.id
    log_survey_step_completed(user_id, "BODY_IDEAL", {"body_ideal_id": variant_id})

    # Удалить все сообщения с вариантами
    message_ids = data.get("body_ideal_message_ids", [])
    await image_sender.delete_messages(bot, callback.message.chat.id, message_ids)

    # Переход к следующему шагу - TZ (часовой пояс)
    await state.set_state(SurveyStates.TZ)

    # Объединяем подтверждение и следующий вопрос в одно сообщение
    combined_message = BODY_IDEAL_SELECTED.format(variant_id=variant_id, label=label) + "\n\n" + TZ_QUESTION
    await callback.message.answer(
        combined_message,
        reply_markup=get_timezone_keyboard(),
        parse_mode="HTML",
        disable_notification=True
    )
    await callback.answer()
