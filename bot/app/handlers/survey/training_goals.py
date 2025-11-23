"""Хендлеры для уровня тренированности и целей по телу."""
from aiogram import Bot, Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from app.states import SurveyStates
from app.texts.survey import (
    TRAINING_LEVEL_LABELS,
    TRAINING_LEVEL_SAVED,
    BODY_GOALS_LABELS,
    BODY_GOALS_QUESTION,
    BODY_GOALS_SELECTED_TEMPLATE,
    BODY_GOALS_MIN_WARNING,
    HEALTH_LIMITATIONS_QUESTION,
    HEALTH_LIMITATIONS_SELECTED_TEMPLATE,
    HEALTH_LIMITATIONS_LABELS,
)
from app.keyboards import get_body_goals_keyboard, get_health_limitations_keyboard
from app.services.events import log_survey_step_completed

router = Router(name="survey_training_goals")


def _format_selected_goals(selected: list[str]) -> str:
    if not selected:
        return "ничего не выбрано"
    return ", ".join(BODY_GOALS_LABELS.get(goal, goal) for goal in selected)


def _format_selected_limitations(selected: list[str]) -> str:
    if not selected:
        return "ничего не выбрано"
    if "none" in selected:
        return HEALTH_LIMITATIONS_LABELS.get("none", "Никаких ограничений")
    return ", ".join(HEALTH_LIMITATIONS_LABELS.get(item, item) for item in selected)


@router.callback_query(F.data.startswith("training_level:"), SurveyStates.TRAINING_LEVEL)
async def process_training_level(callback: CallbackQuery, state: FSMContext):
    """Сохраняет уровень тренированности и открывает выбор целей по телу."""
    parts = callback.data.split(":")
    if len(parts) != 2:
        await callback.answer("❌ Некорректные данные", show_alert=True)
        return

    training_level = parts[1]
    if training_level not in TRAINING_LEVEL_LABELS:
        await callback.answer("❌ Некорректный уровень", show_alert=True)
        return

    await state.update_data(training_level=training_level)
    user_id = callback.from_user.id
    log_survey_step_completed(user_id, "TRAINING_LEVEL", {"training_level": training_level})

    await state.set_state(SurveyStates.BODY_GOALS)

    selected_goals = (await state.get_data()).get("body_goals", [])
    selected_text = BODY_GOALS_SELECTED_TEMPLATE.format(
        selected=_format_selected_goals(selected_goals)
    )

    await callback.message.edit_text(
        TRAINING_LEVEL_SAVED.format(label=TRAINING_LEVEL_LABELS[training_level])
        + "\n\n"
        + BODY_GOALS_QUESTION
        + "\n\n"
        + selected_text,
        reply_markup=get_body_goals_keyboard(selected_goals),
        parse_mode="HTML",
    )

    await state.update_data(last_bot_message_id=callback.message.message_id)
    await callback.answer()


@router.callback_query(F.data.startswith("body_goal:"), SurveyStates.BODY_GOALS)
async def toggle_body_goal(callback: CallbackQuery, state: FSMContext):
    """Тоггл целей по телу."""
    parts = callback.data.split(":")
    if len(parts) != 2:
        await callback.answer("❌ Некорректные данные", show_alert=True)
        return

    goal = parts[1]
    if goal not in BODY_GOALS_LABELS:
        await callback.answer("❌ Некорректный вариант", show_alert=True)
        return

    data = await state.get_data()
    selected = set(data.get("body_goals", []))

    if goal in selected:
        selected.remove(goal)
    else:
        selected.add(goal)

    updated_list = list(selected)
    await state.update_data(body_goals=updated_list)

    selected_text = BODY_GOALS_SELECTED_TEMPLATE.format(
        selected=_format_selected_goals(updated_list)
    )

    training_label = TRAINING_LEVEL_LABELS.get(data.get("training_level"), "не указан")
    message_text = TRAINING_LEVEL_SAVED.format(label=training_label)
    message_text += "\n\n" + BODY_GOALS_QUESTION + "\n\n" + selected_text

    await callback.message.edit_text(
        message_text,
        reply_markup=get_body_goals_keyboard(updated_list),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "body_goals:done", SurveyStates.BODY_GOALS)
async def confirm_body_goals(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Фиксирует цели и открывает выбор текущего типа фигуры."""
    data = await state.get_data()
    selected = data.get("body_goals", []) or []

    if not selected:
        await callback.answer(BODY_GOALS_MIN_WARNING, show_alert=True)
        return

    user_id = callback.from_user.id
    log_survey_step_completed(user_id, "BODY_GOALS", {"body_goals": selected})

    await state.set_state(SurveyStates.HEALTH_LIMITATIONS)

    limitations_selected = data.get("health_limitations", []) or []
    limitations_text = HEALTH_LIMITATIONS_SELECTED_TEMPLATE.format(
        selected=_format_selected_limitations(limitations_selected)
    )

    training_label = TRAINING_LEVEL_LABELS.get(data.get("training_level"), "")
    message_text = TRAINING_LEVEL_SAVED.format(label=training_label) if training_label else ""
    message_text += "\n\n" + BODY_GOALS_SELECTED_TEMPLATE.format(
        selected=_format_selected_goals(selected)
    )
    message_text += "\n\n" + HEALTH_LIMITATIONS_QUESTION + "\n\n" + limitations_text

    await callback.message.edit_text(
        message_text,
        reply_markup=get_health_limitations_keyboard(limitations_selected),
        parse_mode="HTML",
    )

    await state.update_data(last_bot_message_id=callback.message.message_id)
    await callback.answer()
