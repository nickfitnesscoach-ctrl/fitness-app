"""
Хендлеры навигации в опросе Personal Plan.
Включает: отмена опроса, возврат к предыдущему шагу.
"""

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from app.states import SurveyStates
from app.texts.survey import (
    SURVEY_CANCELLED,
    GENDER_QUESTION,
    AGE_QUESTION,
    HEIGHT_QUESTION,
    WEIGHT_QUESTION,
    TARGET_WEIGHT_QUESTION,
    ACTIVITY_QUESTION,
    TRAINING_LEVEL_QUESTION,
    BODY_GOALS_QUESTION,
    BODY_GOALS_SELECTED_TEMPLATE,
    BODY_GOALS_LABELS,
    TRAINING_LEVEL_LABELS,
    TRAINING_LEVEL_SAVED,
    HEALTH_LIMITATIONS_QUESTION,
    HEALTH_LIMITATIONS_SELECTED_TEMPLATE,
    HEALTH_LIMITATIONS_LABELS,
    TZ_QUESTION,
    BODY_NOW_QUESTION_HEADER,
    BODY_IDEAL_QUESTION_HEADER,
)
from app.keyboards import (
    get_gender_keyboard,
    get_target_weight_keyboard,
    get_activity_keyboard,
    get_training_level_keyboard,
    get_body_goals_keyboard,
    get_health_limitations_keyboard,
    get_timezone_keyboard,
)
from app.services.image_sender import image_sender
from app.services.events import log_survey_cancelled

router = Router(name="survey_navigation")


@router.callback_query(F.data == "survey:cancel")
async def cancel_survey(callback: CallbackQuery, state: FSMContext):
    """Отмена опроса."""
    user_id = callback.from_user.id
    current_state = await state.get_state()
    log_survey_cancelled(user_id, current_state)

    await state.clear()
    await callback.message.edit_text(SURVEY_CANCELLED, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "survey:back")
async def go_back(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Универсальный обработчик кнопки 'Назад' для всех шагов опроса."""
    current_state = await state.get_state()

    # Маппинг: текущее состояние -> предыдущее состояние
    back_mapping = {
        SurveyStates.AGE: (SurveyStates.GENDER, GENDER_QUESTION, get_gender_keyboard),
        SurveyStates.HEIGHT: (SurveyStates.AGE, AGE_QUESTION, None),
        SurveyStates.WEIGHT: (SurveyStates.HEIGHT, HEIGHT_QUESTION, None),
        SurveyStates.TARGET_WEIGHT: (SurveyStates.WEIGHT, WEIGHT_QUESTION, None),
        SurveyStates.ACTIVITY: (SurveyStates.TARGET_WEIGHT, TARGET_WEIGHT_QUESTION, get_target_weight_keyboard),
        SurveyStates.TRAINING_LEVEL: (SurveyStates.ACTIVITY, ACTIVITY_QUESTION, get_activity_keyboard),
        SurveyStates.BODY_GOALS: (SurveyStates.TRAINING_LEVEL, TRAINING_LEVEL_QUESTION, get_training_level_keyboard),
        SurveyStates.HEALTH_LIMITATIONS: (SurveyStates.BODY_GOALS, BODY_GOALS_QUESTION, get_body_goals_keyboard),
        SurveyStates.BODY_NOW: (SurveyStates.HEALTH_LIMITATIONS, HEALTH_LIMITATIONS_QUESTION, get_health_limitations_keyboard),
        SurveyStates.BODY_IDEAL: (SurveyStates.BODY_NOW, None, None),
        SurveyStates.TZ: (SurveyStates.BODY_IDEAL, None, None),
        SurveyStates.CONFIRM: (SurveyStates.TZ, TZ_QUESTION, get_timezone_keyboard),
    }

    if current_state not in back_mapping:
        await callback.answer()
        return

    prev_state, question_text, keyboard_func = back_mapping[current_state]

    # Удаляем только текущее сообщение с кнопками
    try:
        await callback.message.delete()
    except Exception:
        pass  # Игнорируем ошибки удаления

    # Специальная обработка для BODY_IDEAL (нужно показать изображения BODY_NOW)
    if current_state == SurveyStates.BODY_IDEAL:
        data = await state.get_data()
        gender = data.get("gender", "female")

        await state.set_state(SurveyStates.BODY_NOW)
        await callback.answer()

        message_ids = await image_sender.send_body_type_options(
            bot=bot,
            chat_id=callback.message.chat.id,
            gender=gender,
            stage="now",
            header_message=BODY_NOW_QUESTION_HEADER
        )

        if message_ids:
            await state.update_data(body_now_message_ids=message_ids)
        return

    # Специальная обработка для TZ (нужно показать изображения для BODY_IDEAL)
    if current_state == SurveyStates.TZ:
        data = await state.get_data()
        gender = data.get("gender", "female")

        await state.set_state(SurveyStates.BODY_IDEAL)
        await callback.answer()

        message_ids = await image_sender.send_body_type_options(
            bot=bot,
            chat_id=callback.message.chat.id,
            gender=gender,
            stage="ideal",
            header_message=BODY_IDEAL_QUESTION_HEADER
        )

        if message_ids:
            await state.update_data(body_ideal_message_ids=message_ids)
        return

    # Специальная обработка для возврата к целям по телу (нужно показать выбранные варианты)
    if prev_state == SurveyStates.BODY_GOALS:
        data = await state.get_data()
        # Очистить ранее отправленные изображения текущего типа фигуры
        try:
            body_now_ids = data.get("body_now_message_ids", [])
            if body_now_ids:
                await image_sender.delete_messages(bot, callback.message.chat.id, body_now_ids)
        except Exception:
            pass
        training_label = TRAINING_LEVEL_LABELS.get(data.get("training_level"), "")
        selected_goals = data.get("body_goals", [])
        selected_text = BODY_GOALS_SELECTED_TEMPLATE.format(
            selected=", ".join(BODY_GOALS_LABELS.get(goal, goal) for goal in selected_goals)
            if selected_goals
            else "ничего не выбрано"
        )

        message_text = TRAINING_LEVEL_SAVED.format(label=training_label)
        message_text += "\n\n" + BODY_GOALS_QUESTION + "\n\n" + selected_text

        await state.set_state(SurveyStates.BODY_GOALS)
        await callback.answer()

        sent_msg = await bot.send_message(
            chat_id=callback.message.chat.id,
            text=message_text,
            reply_markup=get_body_goals_keyboard(selected_goals),
            parse_mode="HTML",
        )
        await state.update_data(last_bot_message_id=sent_msg.message_id)
        return

    # Специальная обработка для возврата к ограничениям по здоровью/питанию
    if prev_state == SurveyStates.HEALTH_LIMITATIONS:
        data = await state.get_data()
        # Очистить ранее отправленные изображения текущего типа фигуры
        try:
            body_now_ids = data.get("body_now_message_ids", [])
            if body_now_ids:
                await image_sender.delete_messages(bot, callback.message.chat.id, body_now_ids)
        except Exception:
            pass

        limitations_selected = data.get("health_limitations", []) or []
        selected_text = HEALTH_LIMITATIONS_SELECTED_TEMPLATE.format(
            selected=", ".join(
                HEALTH_LIMITATIONS_LABELS.get(item, item) for item in limitations_selected
            )
            if limitations_selected
            else "ничего не выбрано"
        )

        await state.set_state(SurveyStates.HEALTH_LIMITATIONS)
        await callback.answer()

        sent_msg = await bot.send_message(
            chat_id=callback.message.chat.id,
            text=HEALTH_LIMITATIONS_QUESTION + "\n\n" + selected_text,
            reply_markup=get_health_limitations_keyboard(limitations_selected),
            parse_mode="HTML",
        )
        await state.update_data(last_bot_message_id=sent_msg.message_id)
        return

    # Стандартная обработка для остальных шагов
    await state.set_state(prev_state)
    await callback.answer()

    keyboard = keyboard_func() if keyboard_func else None

    await bot.send_message(
        chat_id=callback.message.chat.id,
        text=question_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
