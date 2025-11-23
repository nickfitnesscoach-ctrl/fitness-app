"""
Хендлеры команд для запуска опроса Personal Plan.
"""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.config import settings
from app.states import SurveyStates
from app.texts.survey import WELCOME_MESSAGE, GENDER_QUESTION
from app.keyboards import get_start_survey_keyboard, get_gender_keyboard, get_admin_start_keyboard, get_open_webapp_keyboard
from app.services.events import log_survey_started
from app.utils.logger import logger

router = Router(name="survey_commands")


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Команда /start - главная точка входа в бота."""
    user_id = message.from_user.id
    logger.info(f"User {user_id} pressed /start")
    logger.info(f"BOT_ADMIN_ID: {settings.BOT_ADMIN_ID}, WEB_APP_URL: {settings.WEB_APP_URL}")

    # Проверяем, является ли пользователь админом
    if user_id == settings.BOT_ADMIN_ID:
        logger.info(f"User {user_id} IS ADMIN - showing admin keyboard")
        admin_url = f"{settings.WEB_APP_URL}/admin"
        logger.info(f"Admin URL will be: {admin_url}")
        
        # Для админа показываем кнопку открытия Mini App
        await message.answer(
            "👋 <b>Привет, Админ!</b>\n\n"
            f"📱 <b>Откройте панель тренера</b>, чтобы управлять заявками и клиентами.\n\n"
            f"<i>Debug: URL = {admin_url}</i>\n\n"
            "Или начните опрос, если хотите протестировать бота.",
            reply_markup=get_admin_start_keyboard(),
            parse_mode="HTML",
            disable_notification=True
        )
    else:
        logger.info(f"User {user_id} is NOT admin")
        # Для обычных пользователей - стандартное приветствие
        await message.answer(
            WELCOME_MESSAGE,
            reply_markup=get_start_survey_keyboard(),
            parse_mode="HTML",
            disable_notification=True
        )


@router.message(Command("app"))
async def cmd_app(message: Message, state: FSMContext):
    """Команда /app - открыть Mini App (для всех пользователей)."""
    user_id = message.from_user.id
    logger.info(f"User {user_id} requested app")

    await message.answer(
        "📱 <b>Откройте приложение</b>\n\n"
        "Нажмите кнопку ниже, чтобы открыть Mini App.",
        reply_markup=get_open_webapp_keyboard(),
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
    
    logger.info(f"User {user_id} started survey")
    
    # Переходим к первому вопросу - выбор пола
    await state.set_state(SurveyStates.waiting_for_gender)
    await callback.message.answer(
        GENDER_QUESTION,
        reply_markup=get_gender_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()
