"""
Хендлеры подтверждения данных и генерации плана в опросе Personal Plan.
"""

import asyncio
import time

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.config import settings
from app.keyboards import (
    get_contact_trainer_keyboard,
    get_gender_keyboard,
    get_plan_error_keyboard,
)
from app.services.ai import openrouter_client
from app.services.backend_api import BackendAPIError, get_backend_api
from app.services.events import log_ai_error, log_plan_generated, log_survey_completed
from app.states import SurveyStates
from app.texts.survey import (
    CONTACT_TRAINER_CTA,
    GENDER_QUESTION,
    GENERATING_PLAN,
    PLAN_GENERATED_HEADER,
    PLAN_GENERATION_ERROR,
    RETURN_TO_TRACKING,
)
from app.utils.logger import logger
from app.validators import validate_ai_response

from .helpers import _plans_word

router = Router(name="survey_confirmation")


@router.callback_query(F.data == "confirm:yes", SurveyStates.CONFIRM)
async def confirm_and_generate(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Подтверждение данных и запуск генерации плана."""
    # Safety check for from_user
    if not callback.from_user:
        logger.error("Callback received without from_user")
        await callback.answer("❌ Ошибка: данные пользователя недоступны", show_alert=True)
        return

    user_id = callback.from_user.id

    # Проверка: уже в процессе генерации?
    current_state = await state.get_state()
    if current_state == SurveyStates.GENERATE:
        await callback.answer("⏳ Уже генерирую план, подождите...", show_alert=True)
        logger.info(f"User {user_id} tried to confirm twice (race condition prevented)")
        return

    # Проверка rate limit: количество планов за сегодня (через Backend API)
    try:
        backend_api = get_backend_api()
        count_result = await backend_api.count_plans_today(user_id)

        if not count_result["can_create"]:
            plans_today = count_result["count"]
            await callback.answer("⚠️ Превышен лимит", show_alert=True)
            await callback.message.edit_text(
                f"⚠️ <b>Превышен дневной лимит</b>\n\n"
                f"Вы уже сгенерировали <b>{plans_today}</b> {_plans_word(plans_today)} сегодня.\n"
                f"Максимум планов в день: <b>{settings.MAX_PLANS_PER_DAY}</b>.\n\n"
                f"Попробуйте завтра или свяжитесь с тренером для индивидуальной консультации.",
                parse_mode="HTML",
                reply_markup=get_contact_trainer_keyboard(),
            )
            await state.clear()
            logger.warning(f"User {user_id} hit rate limit: {plans_today} plans today")
            return
    except BackendAPIError as e:
        # Если проверка rate limit не удалась, логируем и продолжаем (fail-open)
        logger.error(f"Rate limit check failed for user {user_id}: {e}", exc_info=True)

    # Немедленно перейти в состояние GENERATE перед всеми операциями
    await state.set_state(SurveyStates.GENERATE)

    data = await state.get_data()

    # Показать сообщение о генерации
    try:
        progress_msg = await callback.message.edit_text(GENERATING_PLAN, parse_mode="HTML")
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            # Сообщение уже содержит нужный текст, используем текущее
            progress_msg = callback.message
            logger.debug(f"Message already shows GENERATING_PLAN for user {user_id}, skipping edit")
        else:
            raise
    await callback.answer()

    # Запустить фоновую задачу для обновления прогресса
    async def send_progress_updates():
        """Отправляет промежуточные обновления о прогрессе генерации."""
        for i in range(1, 4):  # 3 обновления: через 10, 20, 30 секунд
            await asyncio.sleep(10)
            try:
                await bot.edit_message_text(
                    chat_id=callback.message.chat.id,
                    message_id=progress_msg.message_id,
                    text=f"⏳ Генерирую ваш персональный план... ({i * 10} сек)",
                    parse_mode="HTML",
                )
            except Exception as e:
                # Игнорируем ошибки редактирования (например, если сообщение уже изменено)
                logger.debug(f"Failed to update progress message: {e}")
                break

    # Запустить обновления в фоне
    progress_task = asyncio.create_task(send_progress_updates())

    # Подготовить payload для ИИ
    payload = {
        "gender": data["gender"],
        "age": data["age"],
        "height_cm": data["height_cm"],
        "weight_kg": float(data["weight_kg"]),
        "target_weight_kg": float(data["target_weight_kg"]) if data.get("target_weight_kg") else None,
        "activity": data["activity"],
        "training_level": data.get("training_level"),
        "body_goals": data.get("body_goals", []),
        "health_limitations": data.get("health_limitations", []),
        "body_now": {"id": data["body_now_id"], "label": data.get("body_now_label", "")},
        "body_ideal": {"id": data["body_ideal_id"], "label": data.get("body_ideal_label", "")},
        "tz": data["tz"],
        "utc_offset_minutes": data["utc_offset_minutes"],
        "notes": "",
    }

    # Определить цель автоматически
    if payload["target_weight_kg"]:
        if payload["target_weight_kg"] < payload["weight_kg"]:
            payload["goal"] = "fat_loss"
        elif payload["target_weight_kg"] > payload["weight_kg"]:
            payload["goal"] = "muscle_gain"
        else:
            payload["goal"] = "maintenance"
    else:
        payload["goal"] = "maintenance"

    # Генерация плана через OpenRouter
    try:
        # Вызов ИИ
        result = await openrouter_client.generate_plan(payload)

        # Остановить обновления прогресса
        progress_task.cancel()

        if not result["success"]:
            # Ошибка при генерации
            log_ai_error(user_id, "generation_failed", result.get("error", "Unknown error"))
            await callback.message.answer(PLAN_GENERATION_ERROR, parse_mode="HTML", disable_notification=True)
            await state.clear()
            return

        ai_text = result["text"]
        ai_model = result["model"]
        prompt_version = result["prompt_version"]

        # Валидация ответа ИИ
        validation = validate_ai_response(ai_text)

        if not validation["valid"]:
            # План не прошёл валидацию
            logger.warning(f"AI response validation failed: {validation['errors']}")
            log_plan_generated(user_id, ai_model, validation_passed=False)

        # Сохранение в Backend API
        saved_successfully = await _perform_save_and_respond(callback, state, ai_text, ai_model, prompt_version)

        if saved_successfully:
            await _show_plan_and_clear_state(callback, state, ai_text)
        # Если не успешно - сообщение уже отправлено внутри хелпера

    except Exception as e:
        # Остановить обновления прогресса
        if "progress_task" in locals():
            progress_task.cancel()

        logger.error(f"Error generating plan: {e}", exc_info=True)
        log_ai_error(user_id, "unexpected_error", str(e))
        await callback.message.answer(PLAN_GENERATION_ERROR, parse_mode="HTML", disable_notification=True)
        await state.clear()


async def _perform_save_and_respond(
    callback: CallbackQuery, state: FSMContext, ai_text: str, ai_model: str, prompt_version: str
) -> bool:
    """
    Вспомогательная функция для сохранения плана и опроса в бэкенд.
    Если ошибка - отправляет сообщение об ошибке (с кнопками retry если уместно).
    Возвращает True в случае успеха.
    """
    user_id = callback.from_user.id
    data = await state.get_data()

    # ПРОВЕРКА TTL: Если черновик старше 30 минут - сбрасываем
    created_at = data.get("error_at") or data.get("ai_created_at")
    if created_at and (time.time() - created_at > 1800):
        logger.warning("FSM Draft TTL expired for user %s", user_id)
        await callback.message.answer(
            "⚠️ <b>Время ожидания истекло</b>\n\n"
            "К сожалению, черновик вашего плана устарел. Пожалуйста, пройдите опрос заново.",
            parse_mode="HTML",
        )
        await state.clear()
        return False

    try:
        backend_api = get_backend_api()

        # 1. Получить или создать пользователя
        await backend_api.get_or_create_user(
            telegram_id=user_id,
            username=callback.from_user.username if callback.from_user else None,
            full_name=callback.from_user.full_name if callback.from_user else None,
        )

        # 2. Сохранить ответы опроса
        survey_response = await backend_api.create_survey(
            telegram_id=user_id,
            gender=data["gender"],
            age=data["age"],
            height_cm=data["height_cm"],
            weight_kg=float(data["weight_kg"]),
            target_weight_kg=float(data["target_weight_kg"]) if data.get("target_weight_kg") else None,
            activity=data["activity"],
            training_level=data.get("training_level"),
            body_goals=data.get("body_goals", []),
            health_limitations=data.get("health_limitations", []),
            body_now_id=data["body_now_id"],
            body_now_label=data.get("body_now_label"),
            body_now_file=data["body_now_file"],
            body_ideal_id=data["body_ideal_id"],
            body_ideal_label=data.get("body_ideal_label"),
            body_ideal_file=data["body_ideal_file"],
            timezone=data["tz"],
            utc_offset_minutes=data["utc_offset_minutes"],
        )

        # 3. Сохранить план
        await backend_api.create_plan(
            telegram_id=user_id,
            survey_id=survey_response["id"],
            ai_text=ai_text,
            ai_model=ai_model,
            prompt_version=prompt_version,
        )

        log_survey_completed(user_id)
        log_plan_generated(user_id, ai_model, validation_passed=data.get("validation_passed", True))
        return True

    except BackendAPIError as api_error:
        rid = api_error.request_id
        msg = api_error.args[0] if api_error.args else str(api_error)
        status_code = getattr(api_error, "status_code", 400)  # Fallback

        # Consistent logging: RID | status_code | error_msg
        logger.error(f"[BackendAPI Error] RID: {rid} | Status: {status_code} | Msg: {msg}")

        # Проверка на лимит (DAILY_LIMIT_REACHED)
        if "DAILY_LIMIT_REACHED" in msg:
            await callback.message.answer(
                "⚠️ <b>Лимит планов исчерпан</b>\n\n"
                "Вы уже создали максимальное количество планов на сегодня (3 плана). "
                "Пожалуйста, попробуйте завтра.\n\n"
                "<i>Ваши ответы сохранены, вы сможете вернуться к ним позже.</i>",
                parse_mode="HTML",
            )
            await state.clear()
            return False

        # Обычная ошибка сохранения - предлагаем Retry только для transient
        if _is_transient(msg, status_code):
            # Сохраняем в FSM на случай retry
            await state.update_data(
                ai_text=ai_text,
                ai_model=ai_model,
                ai_prompt_version=prompt_version,
                error_rid=rid,
                error_at=time.time(),
            )

            await callback.message.answer(
                "❌ <b>Не удалось сохранить ваш план</b>\n\n"
                f"Произошла ошибка при связи с сервером (ID: <code>{rid or 'n/a'}</code>).\n"
                "Вы можете попробовать нажать кнопку «Повторить».",
                parse_mode="HTML",
                reply_markup=get_plan_error_keyboard(),
            )
        else:
            # Non-transient error (Validation, Forbidden, etc.)
            await callback.message.answer(
                "❌ <b>Ошибка при сохранении</b>\n\n"
                "К сожалению, произошла критическая ошибка. Пожалуйста, обратитесь в поддержку\n"
                f"ID запроса: <code>{rid or 'n/a'}</code>",
                parse_mode="HTML",
            )
            await state.clear()

        return False


def _is_transient(error_msg: str, status_code: int) -> bool:
    """Определяет, является ли ошибка временной (стоит ли предлагать Retry)."""
    # 5xx ошибки всегда transient
    if status_code >= 500:
        return True
    # Сетевые ошибки/таймауты (httpx выбрасывает их, в BackendAPIError они мапятся в текст)
    if any(x in error_msg for x in ["Timeout", "ConnectError", "ConnectTimeout"]):
        return True
    # 429 не ретраим (мы его уже обработали выше, но на всякий)
    if status_code == 429:
        return False
    # 4xx обычно не transient (Validation, Forbidden, NotFound)
    return False


async def _show_plan_and_clear_state(callback: CallbackQuery, state: FSMContext, ai_text: str):
    """Показывает план пользователю и очищает состояние."""
    plan_message = PLAN_GENERATED_HEADER + ai_text + RETURN_TO_TRACKING

    # Разбить на несколько сообщений если длинный
    if len(plan_message) > 4096:
        await callback.message.answer(PLAN_GENERATED_HEADER, parse_mode="HTML", disable_notification=True)
        await callback.message.answer(ai_text, parse_mode="HTML", disable_notification=True)
        await callback.message.answer(RETURN_TO_TRACKING, parse_mode="HTML", disable_notification=True)
    else:
        await callback.message.answer(plan_message, parse_mode="HTML", disable_notification=True)

    await callback.message.answer(
        CONTACT_TRAINER_CTA,
        reply_markup=get_contact_trainer_keyboard(),
        parse_mode="HTML",
        disable_notification=True,
    )
    await state.clear()


@router.callback_query(F.data == "confirm:edit", SurveyStates.CONFIRM)
async def confirm_edit(callback: CallbackQuery, state: FSMContext):
    """Возврат к редактированию данных - начинаем опрос заново."""
    await callback.answer()

    # Удаляем сообщение с подтверждением данных
    try:
        await callback.message.delete()
    except Exception:
        pass

    # Очищаем все данные и начинаем с начала
    await state.clear()

    # Отправляем приветственное сообщение и начинаем с первого шага
    await callback.message.answer(
        "🔄 <b>Начинаем опрос заново</b>\n\n" + GENDER_QUESTION,
        reply_markup=get_gender_keyboard(),
        parse_mode="HTML",
        disable_notification=True,
    )

    # Устанавливаем состояние GENDER (первый шаг)
    await state.set_state(SurveyStates.GENDER)


@router.callback_query(F.data == "plan:retry", SurveyStates.GENERATE)
async def process_plan_retry(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Повторная попытка сохранения плана."""
    user_id = callback.from_user.id
    data = await state.get_data()

    ai_text = data.get("ai_text")
    if not ai_text:
        await callback.answer("❌ Ошибка: данные плана потеряны", show_alert=True)
        return

    await callback.answer("⏳ Пробую сохранить ещё раз...")

    success = await _perform_save_and_respond(
        callback, state, ai_text, data.get("ai_model", "unknown"), data.get("ai_prompt_version", "unknown")
    )

    if success:
        # План был успешно сохранён и показан внутри _perform_save_and_respond
        # Удаляем сообщение об ошибке (оно же callback.message в данном контексте)
        try:
            await callback.message.delete()
        except Exception:
            pass
        logger.info(f"User {user_id} successfully saved plan after retry")
    else:
        # Ответ об ошибке уже отправлен внутри
        pass


@router.callback_query(F.data == "plan:cancel", SurveyStates.GENERATE)
async def process_plan_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена после ошибки сохранения."""
    await callback.answer("Отменено")
    await state.clear()
    await callback.message.edit_text(
        "❌ <b>Генерация прервана</b>\n\nПлан не был сохранён. Вы можете начать опрос заново, когда связь наладится.",
        parse_mode="HTML",
    )
