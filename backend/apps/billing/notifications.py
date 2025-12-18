"""
billing/notifications.py

Telegram-уведомления админам о новых PRO подписках.

Фича:
- При успешной оплате PRO подписки (месяц/год) админам в Telegram отправляется карточка:
  • Telegram ID пользователя
  • @username пользователя (если есть)
  • Какой тариф оплатил (PRO месяц / PRO год)
  • Дата окончания подписки
  • Кнопка «Открыть профиль» (inline-кнопка)

Использование:
- Вызывать send_pro_subscription_notification() из handlers.py после успешной активации подписки

Зависимости:
- settings.TELEGRAM_BOT_TOKEN — токен бота
- settings.TELEGRAM_ADMINS — список ID админов (set/list или строка через запятую)
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

import requests
from django.conf import settings

if TYPE_CHECKING:
    from apps.billing.models import Subscription, SubscriptionPlan
    from apps.users.models import Profile

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Константы
# -----------------------------------------------------------------------------

# URL для Telegram Bot API
TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}"


# -----------------------------------------------------------------------------
# Основная функция уведомления
# -----------------------------------------------------------------------------

def send_pro_subscription_notification(
    subscription: "Subscription",
    plan: "SubscriptionPlan",
) -> bool:
    """
    Отправляет уведомление админам о новой PRO подписке.

    Аргументы:
        subscription: объект Subscription с user и end_date
        plan: объект SubscriptionPlan с кодом и названием тарифа

    Возвращает:
        True — если хотя бы одному админу успешно отправлено
        False — если отправка не удалась или нет конфигурации

    Логика:
        - Получаем данные пользователя (telegram_id, username)
        - Формируем красивую карточку с inline-кнопкой
        - Отправляем всем админам из settings.TELEGRAM_ADMINS
    """
    # Проверяем конфигурацию
    bot_token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)
    admin_ids = getattr(settings, "TELEGRAM_ADMINS", None)

    if not bot_token or not admin_ids:
        logger.warning(
            "[PRO_NOTIFICATION] Пропущено: TELEGRAM_BOT_TOKEN или TELEGRAM_ADMINS не настроены"
        )
        return False

    # Парсим список админов (может быть строкой через запятую)
    admin_list = _parse_admin_ids(admin_ids)
    if not admin_list:
        logger.warning("[PRO_NOTIFICATION] Пропущено: пустой список TELEGRAM_ADMINS")
        return False

    # Получаем профиль пользователя
    try:
        profile: Optional["Profile"] = getattr(subscription.user, "profile", None)
    except Exception:
        profile = None

    # Извлекаем данные для карточки
    tg_id = profile.telegram_id if profile else None
    tg_username = profile.telegram_username if profile else None
    full_name = profile.full_name if profile and profile.full_name else subscription.user.username

    # Дата окончания подписки
    end_date_str = _format_date(subscription.end_date)

    # Определяем тип тарифа по коду
    plan_display = _get_plan_display_name(plan)

    # Формируем текст карточки
    message = _build_notification_card(
        tg_id=tg_id,
        tg_username=tg_username,
        full_name=full_name,
        plan_display=plan_display,
        end_date_str=end_date_str,
        plan_price=plan.price,
    )

    # Формируем inline-кнопку «Открыть профиль»
    inline_keyboard = _build_inline_keyboard(tg_id)

    # Отправляем всем админам
    success = False
    for admin_id in admin_list:
        if _send_telegram_message(
            bot_token=bot_token,
            chat_id=admin_id,
            text=message,
            inline_keyboard=inline_keyboard,
        ):
            success = True

    if success:
        logger.info(
            f"[PRO_NOTIFICATION] Отправлено уведомление: user_id={subscription.user_id}, "
            f"plan={plan.code}, end_date={subscription.end_date}"
        )
    else:
        logger.error(
            f"[PRO_NOTIFICATION] Не удалось отправить ни одному админу: user_id={subscription.user_id}"
        )

    return success


# -----------------------------------------------------------------------------
# Вспомогательные функции
# -----------------------------------------------------------------------------

def _parse_admin_ids(admin_ids) -> list:
    """
    Парсит список ID админов из разных форматов.

    Поддерживаемые форматы:
        - set/list/tuple с числами или строками
        - строка с ID через запятую: "123,456,789"
    """
    if isinstance(admin_ids, (set, list, tuple)):
        return [str(x).strip() for x in admin_ids if x]

    if isinstance(admin_ids, str):
        return [x.strip() for x in admin_ids.split(",") if x.strip()]

    return []


def _format_date(dt) -> str:
    """
    Форматирует дату в читаемый формат.

    Примеры:
        datetime(2025, 1, 18) -> "18.01.2025"
    """
    if isinstance(dt, datetime):
        return dt.strftime("%d.%m.%Y")
    if isinstance(dt, date):
        return dt.strftime("%d.%m.%Y")
    return str(dt) if dt else "—"


def _get_plan_display_name(plan: "SubscriptionPlan") -> str:
    """
    Возвращает человекочитаемое название тарифа.

    Логика:
        - Если есть display_name — используем его
        - Иначе анализируем duration_days для определения месяц/год
    """
    if plan.display_name:
        return plan.display_name

    # Определяем по длительности
    days = plan.duration_days or 0
    if days >= 360:
        return "PRO Годовой"
    elif days >= 28:
        return "PRO Месячный"
    else:
        return f"PRO ({days} дн.)"


def _build_notification_card(
    tg_id: Optional[int],
    tg_username: Optional[str],
    full_name: str,
    plan_display: str,
    end_date_str: str,
    plan_price: float,
) -> str:
    """
    Формирует HTML-карточку уведомления о подписке.

    Структура карточки:
        🎉 НОВАЯ ПОДПИСКА PRO
        ━━━━━━━━━━━━━━━━━━
        👤 Имя: {full_name}
        🆔 Telegram ID: {tg_id}
        📧 Username: @{tg_username}
        ━━━━━━━━━━━━━━━━━━
        💎 Тариф: {plan_display}
        💰 Сумма: {plan_price} ₽
        📅 Подписка до: {end_date_str}
    """
    # Формируем username с @
    username_display = f"@{tg_username}" if tg_username else "—"

    card = (
        "🎉 <b>НОВАЯ ПОДПИСКА PRO</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Имя:</b> {_escape_html(full_name)}\n"
        f"🆔 <b>Telegram ID:</b> <code>{tg_id or '—'}</code>\n"
        f"📧 <b>Username:</b> {_escape_html(username_display)}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"💎 <b>Тариф:</b> {_escape_html(plan_display)}\n"
        f"💰 <b>Сумма:</b> {int(plan_price)} ₽\n"
        f"📅 <b>Подписка до:</b> {end_date_str}"
    )

    return card


def _build_inline_keyboard(tg_id: Optional[int]) -> Optional[dict]:
    """
    Формирует inline-клавиатуру с кнопкой «Открыть профиль».

    Кнопка:
        - Если есть tg_id — ссылка tg://user?id={tg_id}
        - Если нет tg_id — кнопка не добавляется

    Формат для Telegram API:
        {"inline_keyboard": [[{"text": "...", "url": "..."}]]}
    """
    if not tg_id:
        return None

    return {
        "inline_keyboard": [
            [
                {
                    "text": "👤 Открыть профиль в Telegram",
                    "url": f"tg://user?id={tg_id}",
                }
            ]
        ]
    }


def _escape_html(text: str) -> str:
    """
    Экранирует HTML-спецсимволы для Telegram HTML parse_mode.

    Заменяет: < > & на HTML entities.
    """
    if not text:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _send_telegram_message(
    bot_token: str,
    chat_id: str,
    text: str,
    inline_keyboard: Optional[dict] = None,
) -> bool:
    """
    Отправляет сообщение через Telegram Bot API.

    Аргументы:
        bot_token: токен Telegram бота
        chat_id: ID чата для отправки
        text: текст сообщения (HTML)
        inline_keyboard: опционально — inline-клавиатура

    Возвращает:
        True — если сообщение успешно отправлено
        False — если произошла ошибка
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }

    if inline_keyboard:
        payload["reply_markup"] = inline_keyboard

    try:
        resp = requests.post(url, json=payload, timeout=10)

        if resp.status_code == 200:
            return True

        # Логируем ошибку от Telegram API
        logger.error(
            f"[TELEGRAM_SEND] Ошибка отправки в chat_id={chat_id}: "
            f"status={resp.status_code}, response={resp.text[:200]}"
        )
        return False

    except requests.RequestException as e:
        logger.error(f"[TELEGRAM_SEND] Ошибка сети при отправке в chat_id={chat_id}: {e}")
        return False
