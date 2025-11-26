"""
Хендлеры подтверждения данных и генерации плана в опросе Personal Plan.
"""

import asyncio

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.config import settings
from app.keyboards import get_contact_trainer_keyboard, get_gender_keyboard
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
                reply_markup=get_contact_trainer_keyboard()
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
    progress_msg = await callback.message.edit_text(GENERATING_PLAN, parse_mode="HTML")
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
                    parse_mode="HTML"
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
        "body_now": {
            "id": data["body_now_id"],
            "label": data.get("body_now_label", "")
        },
        "body_ideal": {
            "id": data["body_ideal_id"],
            "label": data.get("body_ideal_label", "")
        },
        "tz": data["tz"],
        "utc_offset_minutes": data["utc_offset_minutes"],
        "notes": ""
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

        # Сохранить в Backend API с обработкой ошибок
        try:
            backend_api = get_backend_api()

            # Получить или создать пользователя
            await backend_api.get_or_create_user(
                telegram_id=user_id,
                username=callback.from_user.username if callback.from_user else None,
                full_name=callback.from_user.full_name if callback.from_user else None
            )

            # Сохранить ответы опроса
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
                utc_offset_minutes=data["utc_offset_minutes"]
            )

            # Сохранить план
            await backend_api.create_plan(
                telegram_id=user_id,
                survey_id=survey_response["id"],
                ai_text=ai_text,
                ai_model=ai_model,
                prompt_version=prompt_version
            )

            log_survey_completed(user_id)
            log_plan_generated(user_id, ai_model, validation_passed=validation["valid"])

        except BackendAPIError as api_error:
            # Критическая ошибка: план сгенерирован, но не сохранён в Backend API
            logger.critical(f"Backend API save failed after AI generation for user {user_id}: {api_error}", exc_info=True)

            # Отправить план пользователю с предупреждением
            await callback.message.answer(
                f"⚠️ <b>План сгенерирован, но не сохранён в базе данных</b>\n\n"
                f"Пожалуйста, сохраните текст плана:\n\n{ai_text}\n\n"
                f"Обратитесь к администратору для восстановления данных.",
                parse_mode="HTML",
                disable_notification=True
            )
            await state.clear()
            return

        # Отправить план пользователю
        plan_message = PLAN_GENERATED_HEADER + ai_text + RETURN_TO_TRACKING

        # Разбить на несколько сообщений если длинный (Telegram лимит 4096 символов)
        if len(plan_message) > 4096:
            # Отправить заголовок
            await callback.message.answer(PLAN_GENERATED_HEADER, parse_mode="HTML", disable_notification=True)
            # Отправить текст плана
            await callback.message.answer(ai_text, parse_mode="HTML", disable_notification=True)
            # Отправить финальную подсказку
            await callback.message.answer(RETURN_TO_TRACKING, parse_mode="HTML", disable_notification=True)
        else:
            await callback.message.answer(plan_message, parse_mode="HTML", disable_notification=True)

        # Отправить призыв к действию с кнопкой контакта тренера
        await callback.message.answer(
            CONTACT_TRAINER_CTA,
            reply_markup=get_contact_trainer_keyboard(),
            parse_mode="HTML",
            disable_notification=True
        )

        # Очистить FSM состояние
        await state.clear()

    except Exception as e:
        # Остановить обновления прогресса
        progress_task.cancel()

        logger.error(f"Error generating plan: {e}", exc_info=True)
        log_ai_error(user_id, "unexpected_error", str(e))
        await callback.message.answer(PLAN_GENERATION_ERROR, parse_mode="HTML", disable_notification=True)
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
        disable_notification=True
    )

    # Устанавливаем состояние GENDER (первый шаг)
    await state.set_state(SurveyStates.GENDER)
