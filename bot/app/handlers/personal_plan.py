"""
Хендлеры для опроса Personal Plan.
"""

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.config import settings
from app.states import SurveyStates
from app.texts.survey import *
from app.keyboards import *
from app.constants import BODY_LABELS, BODY_COUNTS
from app.validators import (
    validate_age,
    validate_height,
    validate_weight,
    validate_target_weight,
    validate_and_normalize_timezone,
)
from app.services.image_sender import image_sender
from app.services.database import async_session_maker, PlanRepository
from app.services.events import (
    log_survey_started,
    log_survey_step_completed,
    log_survey_cancelled,
)
from app.utils.logger import logger

router = Router(name="personal_plan")


# =============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =============================================================================

def _plans_word(count: int) -> str:
    """
    Правильное склонение слова 'план'.

    Args:
        count: Количество планов

    Returns:
        'план', 'плана' или 'планов'
    """
    if count % 10 == 1 and count % 100 != 11:
        return "план"
    elif 2 <= count % 10 <= 4 and (count % 100 < 10 or count % 100 >= 20):
        return "плана"
    else:
        return "планов"


async def _safe_delete_message(bot: Bot, chat_id: int, message_id: int, user_id: int = None) -> bool:
    """
    Безопасное удаление сообщения с детальной обработкой ошибок.

    Args:
        bot: Bot instance
        chat_id: ID чата
        message_id: ID сообщения для удаления
        user_id: ID пользователя (для логирования)

    Returns:
        True если сообщение удалено, False если не удалось
    """
    from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        return True
    except TelegramBadRequest as e:
        error_msg = str(e).lower()
        if "message to delete not found" in error_msg or "message can't be deleted" in error_msg:
            logger.debug(f"Message {message_id} already deleted or can't be deleted")
        else:
            logger.warning(f"Failed to delete message {message_id}: {e}")
        return False
    except TelegramForbiddenError:
        logger.error(f"Bot blocked by user {user_id} (chat_id={chat_id})")
        return False
    except Exception as e:
        logger.warning(f"Unexpected error deleting message {message_id}: {e}")
        return False


# =============================================================================
# НАЧАЛО ОПРОСА
# =============================================================================

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Команда /start - главная точка входа в бота."""
    user_id = message.from_user.id
    logger.info(f"User {user_id} pressed /start")

    await message.answer(
        WELCOME_MESSAGE,
        reply_markup=get_start_survey_keyboard(),
        parse_mode="HTML",
        disable_notification=True
    )


@router.message(Command("personal_plan"))
async def cmd_personal_plan(message: Message, state: FSMContext):
    """Команда запуска опроса Personal Plan."""
    user_id = message.from_user.id
    logger.info(f"User {user_id} started personal plan survey")

    await message.answer(
        WELCOME_MESSAGE,
        reply_markup=get_start_survey_keyboard(),
        parse_mode="HTML",
        disable_notification=True
    )


@router.callback_query(F.data == "survey:start")
async def start_survey(callback: CallbackQuery, state: FSMContext):
    """Начало опроса после нажатия кнопки."""
    user_id = callback.from_user.id
    log_survey_started(user_id)

    # Очистить старое состояние перед началом нового опроса
    await state.clear()

    await state.set_state(SurveyStates.GENDER)
    await callback.message.edit_text(
        GENDER_QUESTION,
        reply_markup=get_gender_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


# =============================================================================
# ШАГ 1: ПОЛ
# =============================================================================

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


# =============================================================================
# ШАГ 2: ВОЗРАСТ
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
# ШАГ 3: РОСТ
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
# ШАГ 4: ВЕС
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
# ШАГ 5: ЦЕЛЕВОЙ ВЕС (опционально)
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


# =============================================================================
# ШАГ 6: УРОВЕНЬ АКТИВНОСТИ
# =============================================================================

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

    # Переход к следующему шагу - BODY_NOW (показ изображений)
    await state.set_state(SurveyStates.BODY_NOW)
    await callback.answer()

    # Получить данные для удаления предыдущего сообщения
    data = await state.get_data()
    last_msg_id = data.get("last_bot_message_id")

    # Удаляем предыдущее сообщение бота (подтверждение целевого веса)
    try:
        if last_msg_id:
            await bot.delete_message(chat_id=callback.message.chat.id, message_id=last_msg_id)
    except Exception:
        pass

    # Удаляем сообщение с вопросом об активности
    try:
        await callback.message.delete()
    except Exception:
        pass

    # Получить пол для показа правильных изображений
    gender = data.get("gender", "female")

    # Отправить изображения вариантов типов фигуры
    message_ids = await image_sender.send_body_type_options(
        bot=bot,
        chat_id=callback.message.chat.id,
        gender=gender,
        stage="now",
        header_message=BODY_NOW_QUESTION_HEADER
    )

    # Сохранить message_ids для последующего удаления
    await state.update_data(body_now_message_ids=message_ids)


# =============================================================================
# ШАГ 7: ТЕКУЩИЙ ТИП ФИГУРЫ
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
# ШАГ 8: ИДЕАЛЬНЫЙ ТИП ФИГУРЫ
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


# =============================================================================
# ШАГ 9: ЧАСОВОЙ ПОЯС
# =============================================================================

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


# =============================================================================
# ПОДТВЕРЖДЕНИЕ ДАННЫХ
# =============================================================================

async def show_confirmation(message: Message, state: FSMContext) -> None:
    """Показывает подтверждение всех введённых данных."""
    data = await state.get_data()

    # Форматирование данных
    confirmation_text = CONFIRM_DATA_HEADER + CONFIRM_DATA_TEMPLATE.format(
        gender=format_gender(data.get("gender")),
        age=data.get("age"),
        height=data.get("height_cm"),
        weight=data.get("weight_kg"),
        target_weight=format_target_weight(data.get("target_weight_kg")),
        activity=ACTIVITY_LABELS.get(data.get("activity"), data.get("activity")),
        body_now_id=data.get("body_now_id"),
        body_now_label=data.get("body_now_label"),
        body_ideal_id=data.get("body_ideal_id"),
        body_ideal_label=data.get("body_ideal_label"),
        tz=data.get("tz"),
        utc_offset=format_utc_offset(data.get("utc_offset_minutes", 0))
    )

    confirmation_text += "\n" + CONFIRM_QUESTION

    await message.answer(
        confirmation_text,
        reply_markup=get_confirmation_keyboard(),
        parse_mode="HTML",
        disable_notification=True
    )


# =============================================================================
# НАВИГАЦИЯ: ОТМЕНА И НАЗАД
# =============================================================================

@router.callback_query(F.data == "survey:cancel")
async def cancel_survey(callback: CallbackQuery, state: FSMContext):
    """Отмена опроса."""
    user_id = callback.from_user.id
    current_state = await state.get_state()
    log_survey_cancelled(user_id, current_state)

    await state.clear()
    await callback.message.edit_text(SURVEY_CANCELLED, parse_mode="HTML")
    await callback.answer()


# =============================================================================
# ПОДТВЕРЖДЕНИЕ И ГЕНЕРАЦИЯ ПЛАНА
# =============================================================================

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

    # Проверка rate limit: количество планов за сегодня
    try:
        async with async_session_maker() as session:
            plans_today = await PlanRepository.count_plans_today(session, user_id)
            if plans_today >= settings.MAX_PLANS_PER_DAY:
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
    except Exception as e:
        # Если проверка rate limit не удалась, логируем и продолжаем (fail-open)
        logger.error(f"Rate limit check failed for user {user_id}: {e}", exc_info=True)

    # Немедленно перейти в состояние GENERATE перед всеми операциями
    await state.set_state(SurveyStates.GENERATE)

    data = await state.get_data()

    # Показать сообщение о генерации
    progress_msg = await callback.message.edit_text(GENERATING_PLAN, parse_mode="HTML")
    await callback.answer()

    # Запустить фоновую задачу для обновления прогресса
    import asyncio

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
    from app.services.ai import openrouter_client
    from app.validators import validate_ai_response
    from app.services.database import async_session_maker, UserRepository, SurveyRepository, PlanRepository
    from app.services.events import log_survey_completed, log_plan_generated, log_ai_error

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

        # Сохранить в БД с обработкой ошибок
        try:
            async with async_session_maker() as session:
                # Получить или создать пользователя
                user = await UserRepository.get_or_create(
                    session,
                    tg_id=user_id,
                    username=callback.from_user.username if callback.from_user else None,
                    full_name=callback.from_user.full_name if callback.from_user else None
                )

                # Сохранить ответы опроса
                survey = await SurveyRepository.create_survey_answer(
                    session,
                    user_id=user.id,
                    data=data
                )

                # Сохранить план
                plan = await PlanRepository.create_plan(
                    session,
                    user_id=user.id,
                    survey_answer_id=survey.id,
                    ai_text=ai_text,
                    ai_model=ai_model,
                    prompt_version=prompt_version
                )

            log_survey_completed(user_id)
            log_plan_generated(user_id, ai_model, validation_passed=validation["valid"])
        except Exception as db_error:
            # Критическая ошибка: план сгенерирован, но не сохранён в БД
            logger.critical(f"DB save failed after AI generation for user {user_id}: {db_error}", exc_info=True)

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


# =============================================================================
# КНОПКА "НАЗАД" - НАВИГАЦИЯ ПО ШАГАМ
# =============================================================================

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
        SurveyStates.BODY_NOW: (SurveyStates.ACTIVITY, ACTIVITY_QUESTION, get_activity_keyboard),
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

    # Специальная обработка для BODY_NOW (нужно показать изображения)
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
