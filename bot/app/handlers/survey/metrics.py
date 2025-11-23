"""
Хендлеры ввода метрических данных в опросе Personal Plan.
Включает: возраст, рост, вес, целевой вес.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.states import SurveyStates
from app.texts.survey import (
    AGE_INVALID, AGE_CONFIRMED, HEIGHT_QUESTION,
    HEIGHT_INVALID, HEIGHT_CONFIRMED, WEIGHT_QUESTION,
    WEIGHT_INVALID, WEIGHT_CONFIRMED, TARGET_WEIGHT_QUESTION,
    TARGET_WEIGHT_INVALID, TARGET_WEIGHT_CONFIRMED, ACTIVITY_QUESTION,
    TARGET_WEIGHT_SKIPPED
)
from app.keyboards import get_empty_keyboard, get_target_weight_keyboard, get_activity_keyboard
from app.validators import validate_age, validate_height, validate_weight, validate_target_weight
from app.services.events import log_survey_step_completed
from .helpers import _safe_delete_message

router = Router(name="survey_metrics")


# =============================================================================
# ВОЗРАСТ
# =============================================================================

@router.message(SurveyStates.AGE, F.text)
async def process_age(message: Message, state: FSMContext):
    """Обработка ввода возраста."""
    age = validate_age(message.text)

    if age is None:
        # Удалить сообщение пользователя с некорректным вводом
        try:
            await message.delete()
        except Exception:
            pass
        error_msg = await message.answer(AGE_INVALID, parse_mode="HTML", disable_notification=True)
        await state.update_data(last_bot_message_id=error_msg.message_id)
        return

    await state.update_data(age=age)
    user_id = message.from_user.id
    log_survey_step_completed(user_id, "AGE", {"age": age})

    # Удаляем предыдущее сообщение бота и сообщение пользователя
    data = await state.get_data()
    last_msg_id = data.get("last_bot_message_id")
    if last_msg_id:
        await _safe_delete_message(message.bot, message.chat.id, last_msg_id, message.from_user.id)
    await _safe_delete_message(message.bot, message.chat.id, message.message_id, message.from_user.id)

    # Переход к следующему шагу
    await state.set_state(SurveyStates.HEIGHT)
    sent_msg = await message.answer(
        AGE_CONFIRMED.format(age=age) + "\n\n" + HEIGHT_QUESTION,
        reply_markup=get_empty_keyboard(),
        parse_mode="HTML",
        disable_notification=True
    )
    await state.update_data(last_bot_message_id=sent_msg.message_id)


# =============================================================================
# РОСТ
# =============================================================================

@router.message(SurveyStates.HEIGHT, F.text)
async def process_height(message: Message, state: FSMContext):
    """Обработка ввода роста."""
    height = validate_height(message.text)

    if height is None:
        # Удалить сообщение пользователя с некорректным вводом
        try:
            await message.delete()
        except Exception:
            pass
        error_msg = await message.answer(HEIGHT_INVALID, parse_mode="HTML", disable_notification=True)
        await state.update_data(last_bot_message_id=error_msg.message_id)
        return

    await state.update_data(height_cm=height)
    user_id = message.from_user.id
    log_survey_step_completed(user_id, "HEIGHT", {"height_cm": height})

    # Удаляем предыдущее сообщение бота и сообщение пользователя
    data = await state.get_data()
    last_msg_id = data.get("last_bot_message_id")
    if last_msg_id:
        await _safe_delete_message(message.bot, message.chat.id, last_msg_id, message.from_user.id)
    await _safe_delete_message(message.bot, message.chat.id, message.message_id, message.from_user.id)

    # Переход к следующему шагу
    await state.set_state(SurveyStates.WEIGHT)
    sent_msg = await message.answer(
        HEIGHT_CONFIRMED.format(height=height) + "\n\n" + WEIGHT_QUESTION,
        reply_markup=get_empty_keyboard(),
        parse_mode="HTML",
        disable_notification=True
    )
    await state.update_data(last_bot_message_id=sent_msg.message_id)


# =============================================================================
# ВЕС
# =============================================================================

@router.message(SurveyStates.WEIGHT, F.text)
async def process_weight(message: Message, state: FSMContext):
    """Обработка ввода веса."""
    weight = validate_weight(message.text)

    if weight is None:
        # Удалить сообщение пользователя с некорректным вводом
        try:
            await message.delete()
        except Exception:
            pass
        error_msg = await message.answer(WEIGHT_INVALID, parse_mode="HTML", disable_notification=True)
        await state.update_data(last_bot_message_id=error_msg.message_id)
        return

    await state.update_data(weight_kg=weight)
    user_id = message.from_user.id
    log_survey_step_completed(user_id, "WEIGHT", {"weight_kg": weight})

    # Удаляем предыдущее сообщение бота и сообщение пользователя
    data = await state.get_data()
    last_msg_id = data.get("last_bot_message_id")
    if last_msg_id:
        await _safe_delete_message(message.bot, message.chat.id, last_msg_id, message.from_user.id)
    await _safe_delete_message(message.bot, message.chat.id, message.message_id, message.from_user.id)

    # Переход к следующему шагу
    await state.set_state(SurveyStates.TARGET_WEIGHT)
    sent_msg = await message.answer(
        WEIGHT_CONFIRMED.format(weight=weight) + "\n\n" + TARGET_WEIGHT_QUESTION,
        reply_markup=get_target_weight_keyboard(),
        parse_mode="HTML",
        disable_notification=True
    )
    await state.update_data(last_bot_message_id=sent_msg.message_id)


# =============================================================================
# ЦЕЛЕВОЙ ВЕС
# =============================================================================

@router.message(SurveyStates.TARGET_WEIGHT, F.text)
async def process_target_weight_text(message: Message, state: FSMContext):
    """Обработка ввода целевого веса."""
    data = await state.get_data()
    current_weight = data.get("weight_kg")

    # Валидация целевого веса (включает проверку числа и отличия от текущего)
    target_weight = validate_target_weight(message.text, current_weight)

    if target_weight is None:
        # Удалить сообщение пользователя с некорректным вводом
        try:
            await message.delete()
        except Exception:
            pass
        error_msg = await message.answer(TARGET_WEIGHT_INVALID, parse_mode="HTML", disable_notification=True)
        await state.update_data(last_bot_message_id=error_msg.message_id)
        return

    await state.update_data(target_weight_kg=target_weight)
    user_id = message.from_user.id
    log_survey_step_completed(user_id, "TARGET_WEIGHT", {"target_weight_kg": target_weight})

    # Удаляем предыдущее сообщение бота и сообщение пользователя
    data = await state.get_data()
    last_msg_id = data.get("last_bot_message_id")
    if last_msg_id:
        await _safe_delete_message(message.bot, message.chat.id, last_msg_id, message.from_user.id)
    await _safe_delete_message(message.bot, message.chat.id, message.message_id, message.from_user.id)

    # Переход к следующему шагу
    await state.set_state(SurveyStates.ACTIVITY)
    sent_msg = await message.answer(
        TARGET_WEIGHT_CONFIRMED.format(target_weight=target_weight) + "\n\n" + ACTIVITY_QUESTION,
        reply_markup=get_activity_keyboard(),
        parse_mode="HTML",
        disable_notification=True
    )
    await state.update_data(last_bot_message_id=sent_msg.message_id)


@router.callback_query(F.data == "target_weight:skip", SurveyStates.TARGET_WEIGHT)
async def process_target_weight_skip(callback: CallbackQuery, state: FSMContext):
    """Пропуск шага целевого веса."""
    await state.update_data(target_weight_kg=None)
    user_id = callback.from_user.id
    log_survey_step_completed(user_id, "TARGET_WEIGHT", {"target_weight_kg": None})

    # Переход к следующему шагу
    await state.set_state(SurveyStates.ACTIVITY)

    # Удаляем старое сообщение и отправляем новое (чтобы его можно было удалить позже)
    await callback.message.delete()
    sent_msg = await callback.message.answer(
        TARGET_WEIGHT_SKIPPED + "\n\n" + ACTIVITY_QUESTION,
        reply_markup=get_activity_keyboard(),
        parse_mode="HTML",
        disable_notification=True
    )
    await state.update_data(last_bot_message_id=sent_msg.message_id)
    await callback.answer()
