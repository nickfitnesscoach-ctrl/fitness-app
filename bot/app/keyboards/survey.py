"""
Клавиатуры для опроса Personal Plan.
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import settings
from app.constants import ACTIVITY_LEVELS, POPULAR_TIMEZONES
from app.texts.survey import (
    BODY_GOALS_LABELS,
    HEALTH_LIMITATIONS_LABELS,
    TRAINING_LEVEL_LABELS,
)


def get_gender_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора пола."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👨 Мужской", callback_data="gender:male"),
        InlineKeyboardButton(text="👩 Женский", callback_data="gender:female"),
    )
    return builder.as_markup()


def get_activity_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора уровня активности."""
    builder = InlineKeyboardBuilder()

    for key, data in ACTIVITY_LEVELS.items():
        builder.row(InlineKeyboardButton(text=data["label"], callback_data=f"activity:{key}"))

    return builder.as_markup()


def get_training_level_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора уровня тренированности."""
    builder = InlineKeyboardBuilder()

    for key, label in TRAINING_LEVEL_LABELS.items():
        builder.row(InlineKeyboardButton(text=label, callback_data=f"training_level:{key}"))

    return builder.as_markup()


def get_body_goals_keyboard(selected: list[str] | None = None) -> InlineKeyboardMarkup:
    """Клавиатура для множественного выбора целей по телу."""
    selected = set(selected or [])
    builder = InlineKeyboardBuilder()

    for key, label in BODY_GOALS_LABELS.items():
        prefix = "✅ " if key in selected else "▫️ "
        builder.row(InlineKeyboardButton(text=f"{prefix}{label}", callback_data=f"body_goal:{key}"))

    builder.row(InlineKeyboardButton(text="✅ Готово", callback_data="body_goals:done"))

    return builder.as_markup()


def get_health_limitations_keyboard(selected: list[str] | None = None) -> InlineKeyboardMarkup:
    """Клавиатура для множественного выбора ограничений по здоровью/питанию."""
    selected = set(selected or [])
    builder = InlineKeyboardBuilder()

    for key, label in HEALTH_LIMITATIONS_LABELS.items():
        prefix = "✅ " if key in selected else "▫️ "
        builder.row(InlineKeyboardButton(text=f"{prefix}{label}", callback_data=f"health_limit:{key}"))

    builder.row(InlineKeyboardButton(text="✅ Готово", callback_data="health_limitations:done"))

    return builder.as_markup()


def get_body_type_keyboard(variant_id: int) -> InlineKeyboardMarkup:
    """Клавиатура под одной картинкой типа фигуры."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=f"✅ Выбрать вариант {variant_id}", callback_data=f"body:{variant_id}"))
    return builder.as_markup()


def get_body_navigation_keyboard(stage: str) -> InlineKeyboardMarkup:
    """Клавиатура навигации после показа всех вариантов тела."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔄 Посмотреть ещё раз", callback_data=f"body_review:{stage}"))
    return builder.as_markup()


def get_timezone_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора часового пояса."""
    builder = InlineKeyboardBuilder()

    tz_items = list(POPULAR_TIMEZONES.items())
    for i in range(0, len(tz_items), 2):
        row_buttons = []
        for j in range(2):
            if i + j < len(tz_items):
                tz_key, tz_data = tz_items[i + j]
                row_buttons.append(
                    InlineKeyboardButton(
                        text=f"{tz_data['label']} (UTC{tz_data['offset']})", callback_data=f"tz:{tz_key}"
                    )
                )
        builder.row(*row_buttons)

    builder.row(InlineKeyboardButton(text="✏️ Другой часовой пояс...", callback_data="tz:manual"))

    return builder.as_markup()


def get_target_weight_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для шага целевого веса."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➡️ Пропустить (поддержание веса)", callback_data="target_weight:skip"))
    return builder.as_markup()


def get_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения данных."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Всё верно, продолжить", callback_data="confirm:yes"),
        InlineKeyboardButton(text="✏️ Изменить данные", callback_data="confirm:edit"),
    )
    return builder.as_markup()


def get_empty_keyboard() -> InlineKeyboardMarkup:
    """Пустая клавиатура."""
    builder = InlineKeyboardBuilder()
    return builder.as_markup()


def get_start_survey_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для запуска опроса."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🚀 Начать опрос", callback_data="survey:start"))
    return builder.as_markup()


def get_contact_trainer_keyboard(trainer_username: str = None) -> InlineKeyboardMarkup:
    """Клавиатура со ссылкой на тренера."""
    builder = InlineKeyboardBuilder()

    if trainer_username:
        url = f"https://t.me/{trainer_username}"
    else:
        url = f"https://t.me/{settings.TRAINER_USERNAME}"

    builder.row(InlineKeyboardButton(text="✉️ Написать тренеру", url=url))

    return builder.as_markup()


def get_open_webapp_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура для КЛИЕНТА - открывает / (КБЖУ трекер на главной).
    """
    from aiogram.types import WebAppInfo

    builder = InlineKeyboardBuilder()

    if settings.WEB_APP_URL:
        # Клиенты идут на главную / - там КБЖУ трекер
        builder.row(InlineKeyboardButton(text="📱 Открыть КБЖУ трекер", web_app=WebAppInfo(url=settings.WEB_APP_URL)))

    builder.row(InlineKeyboardButton(text="✉️ Написать тренеру", url=f"https://t.me/{settings.TRAINER_USERNAME}"))

    return builder.as_markup()


def get_admin_start_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура для АДМИНА - открывает /panel (панель тренера).
    """
    from aiogram.types import WebAppInfo

    builder = InlineKeyboardBuilder()

    if settings.WEB_APP_URL:
        # Админ идёт на /panel - панель тренера
        admin_url = f"{settings.WEB_APP_URL}/panel"
        builder.row(InlineKeyboardButton(text="📱 Открыть панель тренера", web_app=WebAppInfo(url=admin_url)))

    builder.row(InlineKeyboardButton(text="🚀 Начать опрос (тест)", callback_data="survey:start"))

    builder.row(InlineKeyboardButton(text="✉️ Написать тренеру", url=f"https://t.me/{settings.TRAINER_USERNAME}"))

    return builder.as_markup()


def get_plan_error_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура при ошибке сохранения плана."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔁 Повторить", callback_data="plan:retry"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="plan:cancel"),
    )
    return builder.as_markup()
