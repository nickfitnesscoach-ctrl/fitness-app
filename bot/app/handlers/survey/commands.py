"""Хендлеры команд для запуска опроса Personal Plan."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import settings
from app.keyboards import get_gender_keyboard, get_open_webapp_keyboard
from app.services.events import log_survey_started
from app.states import SurveyStates
from app.texts.start import (
    ADMIN_GREETING,
    ADMIN_PANEL_HINT,
    ADMIN_PANEL_NOT_CONFIGURED,
    ADMIN_SURVEY_PROMPT,
    START_SURVEY_BUTTON_ADMIN,
    START_SURVEY_BUTTON_USER,
)
from app.texts.survey import GENDER_QUESTION, WELCOME_MESSAGE
from app.utils.logger import logger

router = Router(name="survey_commands")


def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором."""
    return user_id in settings.admin_ids


def build_start_message(*, is_admin: bool, panel_url: str | None) -> str:
    """Формирует текст стартового сообщения."""
    if not is_admin:
        return WELCOME_MESSAGE

    parts: list[str] = [ADMIN_GREETING, ADMIN_PANEL_HINT]
    if panel_url:
        logger.info("[START] Панель тренера настроена: %s", panel_url)
    else:
        logger.warning(
            "[START] TRAINER_PANEL_BASE_URL не задан — кнопка панели тренера скрыта"
        )
        parts.append(f"<i>{ADMIN_PANEL_NOT_CONFIGURED}</i>")

    parts.append(ADMIN_SURVEY_PROMPT)
    return "\n\n".join(parts)


def build_start_keyboard(*, is_admin: bool, panel_url: str | None) -> InlineKeyboardMarkup:
    """Формирует клавиатуру стартового сообщения."""
    builder = InlineKeyboardBuilder()

    start_button_text = START_SURVEY_BUTTON_ADMIN if is_admin else START_SURVEY_BUTTON_USER
    builder.row(
        InlineKeyboardButton(text=start_button_text, callback_data="survey:start")
    )

    if is_admin:
        if panel_url:
            web_app_url = f"{panel_url.rstrip('/')}/admin/"
            panel_button = InlineKeyboardButton(
                text="📟 Открыть панель тренера",
                web_app=WebAppInfo(url=web_app_url),
            )
            builder.row(panel_button)
            logger.info("[START] Добавлена WebApp кнопка панели тренера: %s", web_app_url)
    else:
        builder.row(
            InlineKeyboardButton(
                text="✉️ Написать тренеру",
                url=f"https://t.me/{settings.TRAINER_USERNAME}",
            )
        )

    logger.info(
        "[START] Сформирована клавиатура: is_admin=%s, panel_button=%s",
        is_admin,
        bool(panel_url and is_admin),
    )
    return builder.as_markup()


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Команда /start - главная точка входа в бота."""
    user_id = message.from_user.id
    logger.info("[START] Пользователь %s вызвал /start", user_id)

    admin_user = is_admin(user_id)
    panel_url = settings.TRAINER_PANEL_BASE_URL.rstrip("/") if settings.TRAINER_PANEL_BASE_URL else None
    logger.info(
        "[START] Данные окружения: TRAINER_PANEL_BASE_URL=%s, WEB_APP_URL=%s, admin_ids=%s",
        settings.TRAINER_PANEL_BASE_URL,
        settings.WEB_APP_URL,
        settings.admin_ids,
    )

    text = build_start_message(is_admin=admin_user, panel_url=panel_url)
    keyboard = build_start_keyboard(is_admin=admin_user, panel_url=panel_url)

    await message.answer(
        text,
        reply_markup=keyboard,
        parse_mode="HTML",
        disable_notification=True,
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
        reply_markup=build_start_keyboard(is_admin=False, panel_url=None),
        parse_mode="HTML",
        disable_notification=True
    )


@router.callback_query(F.data == "survey:start")
async def start_survey(callback: CallbackQuery, state: FSMContext):
    """Начало опроса после нажатия кнопки."""
    user_id = callback.from_user.id
    log_survey_started(user_id)

    logger.info("[SURVEY] Пользователь %s нажал кнопку старта опроса", user_id)

    # Переходим к первому вопросу - выбор пола
    await state.set_state(SurveyStates.GENDER)
    await callback.message.answer(
        GENDER_QUESTION,
        reply_markup=get_gender_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()
