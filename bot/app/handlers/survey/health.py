"""Хендлеры для шага ограничений по здоровью и питанию в опросе Personal Plan."""

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from app.states import SurveyStates
from app.texts.survey import (
    HEALTH_LIMITATIONS_QUESTION,
    HEALTH_LIMITATIONS_LABELS,
    HEALTH_LIMITATIONS_SELECTED_TEMPLATE,
    HEALTH_LIMITATIONS_MIN_WARNING,
    BODY_NOW_QUESTION_HEADER,
)
from app.keyboards import get_health_limitations_keyboard
from app.services.events import log_survey_step_completed
from app.services.image_sender import image_sender
from .helpers import _safe_delete_message

router = Router(name="survey_health_limitations")


def _format_selected_limitations(selected: list[str]) -> str:
    if not selected:
        return "ничего не выбрано"
    if "none" in selected:
        return HEALTH_LIMITATIONS_LABELS.get("none", "Никаких ограничений")
    return ", ".join(HEALTH_LIMITATIONS_LABELS.get(item, item) for item in selected)


@router.callback_query(F.data.startswith("health_limit:"), SurveyStates.HEALTH_LIMITATIONS)
async def toggle_health_limitation(callback: CallbackQuery, state: FSMContext):
    """Тоггл выбора ограничений по здоровью/питанию."""
    parts = callback.data.split(":")
    if len(parts) != 2:
        await callback.answer("❌ Некорректные данные", show_alert=True)
        return

    limitation = parts[1]
    if limitation not in HEALTH_LIMITATIONS_LABELS:
        await callback.answer("❌ Некорректный вариант", show_alert=True)
        return

    data = await state.get_data()
    selected = set(data.get("health_limitations", []))

    if limitation == "none":
        selected = {"none"}
    else:
        selected.discard("none")
        if limitation in selected:
            selected.remove(limitation)
        else:
            selected.add(limitation)

    updated = list(selected)
    await state.update_data(health_limitations=updated)

    selected_text = HEALTH_LIMITATIONS_SELECTED_TEMPLATE.format(
        selected=_format_selected_limitations(updated)
    )

    await callback.message.edit_text(
        HEALTH_LIMITATIONS_QUESTION + "\n\n" + selected_text,
        reply_markup=get_health_limitations_keyboard(updated),
        parse_mode="HTML",
    )
    await state.update_data(last_bot_message_id=callback.message.message_id)
    await callback.answer()


@router.callback_query(F.data == "health_limitations:done", SurveyStates.HEALTH_LIMITATIONS)
async def confirm_health_limitations(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Фиксирует ограничения и переходит к выбору текущего типа фигуры."""
    data = await state.get_data()
    selected = data.get("health_limitations", []) or []

    if not selected:
        await callback.answer(HEALTH_LIMITATIONS_MIN_WARNING, show_alert=True)
        return

    user_id = callback.from_user.id
    log_survey_step_completed(user_id, "HEALTH_LIMITATIONS", {"health_limitations": selected})

    await state.set_state(SurveyStates.BODY_NOW)

    last_msg_id = data.get("last_bot_message_id")
    if last_msg_id:
        await _safe_delete_message(bot, callback.message.chat.id, last_msg_id, user_id)
    try:
        await callback.message.delete()
    except Exception:
        pass

    gender = data.get("gender", "female")

    message_ids = await image_sender.send_body_type_options(
        bot=bot,
        chat_id=callback.message.chat.id,
        gender=gender,
        stage="now",
        header_message=BODY_NOW_QUESTION_HEADER,
    )

    await state.update_data(body_now_message_ids=message_ids)
    await callback.answer()
