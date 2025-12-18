"""
Бизнес-обработчики webhook событий YooKassa.

Философия:
- views.py отвечает за безопасность + идемпотентность + логирование входящего webhook
- handlers.py отвечает за бизнес-логику (что делать с Payment/Subscription)
- utils.py отвечает за утилиты (IP allowlist и т.п.)

ВАЖНО:
- Мы НИКОГДА не доверяем фронтенду сумму/дни/план. Всё берём из БД.
- Мы НЕ "угадываем" состояние — работаем строго через текущие статусы в БД.
- Всё, что может прийти повторно, должно обрабатываться безопасно (идемпотентно).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from django.db import transaction
from django.utils import timezone

from apps.billing.models import Payment, Refund, SubscriptionPlan
from apps.billing.services import activate_or_extend_subscription, invalidate_user_plan_cache
from apps.billing.notifications import send_pro_subscription_notification

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Публичная точка входа для views.py
# ---------------------------------------------------------------------

def handle_yookassa_event(*, event_type: str, payload: Dict[str, Any]) -> None:
    """
    Главный роутер событий.

    event_type примеры (YooKassa):
    - payment.succeeded
    - payment.canceled
    - payment.waiting_for_capture
    - refund.succeeded

    payload структура:
    {
      "type": "notification",
      "event": "payment.succeeded",
      "object": {...}
    }
    """
    handlers = {
        "payment.succeeded": _handle_payment_succeeded,
        "payment.canceled": _handle_payment_canceled,
        "payment.waiting_for_capture": _handle_payment_waiting_for_capture,
        "refund.succeeded": _handle_refund_succeeded,
    }

    handler = handlers.get(event_type)
    if not handler:
        # Неизвестное событие — не ошибка. Просто логируем и выходим.
        logger.info(f"Unhandled YooKassa webhook event: {event_type}")
        return

    handler(payload)


# ---------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------

def _handle_payment_succeeded(payload: Dict[str, Any]) -> None:
    """
    payment.succeeded:
    - находим локальный Payment по yookassa_payment_id
    - отмечаем SUCCEEDED
    - сохраняем payment_method_id (если пришёл и разрешено save_payment_method)
    - продлеваем/активируем подписку на duration_days плана (через сервис)
    - обновляем Subscription payment method info (для автопродления)
    - инвалидируем кеш плана пользователя
    """
    obj = payload.get("object") or {}
    yk_payment_id = obj.get("id")
    if not yk_payment_id:
        raise ValueError("payment.succeeded payload has no object.id")

    with transaction.atomic():
        # IMPORTANT: do NOT select_related() on nullable FK fields here.
        # subscription AND plan are nullable -> LEFT OUTER JOIN -> PostgreSQL forbids FOR UPDATE on nullable side.
        # We only select_related("user") which is NOT NULL.
        payment = (
            Payment.objects.select_for_update()
            .select_related("user")
            .get(yookassa_payment_id=yk_payment_id)
        )

        # Идемпотентность по внутреннему статусу:
        # если уже успешно обработан — выходим без ошибок
        if payment.status == "SUCCEEDED":
            logger.info(f"[payment.succeeded] already processed: payment_id={payment.id}")
            return

        # Если по каким-то причинам уже REFUNDED/CANCELED — тоже не ломаемся
        if payment.status in {"REFUNDED", "CANCELED", "FAILED"}:
            logger.warning(
                f"[payment.succeeded] ignored due to status={payment.status}: "
                f"payment_id={payment.id}, yk_id={yk_payment_id}"
            )
            return

        # Достаём payment_method (может отсутствовать)
        payment_method_id, card_mask, card_brand = _extract_payment_method_info(obj)

        # 1) Помечаем платёж успешным
        payment.status = "SUCCEEDED"
        payment.paid_at = timezone.now()
        payment.webhook_processed_at = timezone.now()

        # сохраняем payment_method_id в Payment, если разрешено
        if payment.save_payment_method and payment_method_id:
            payment.yookassa_payment_method_id = payment_method_id

        payment.save(
            update_fields=[
                "status",
                "paid_at",
                "webhook_processed_at",
                "yookassa_payment_method_id",
                "updated_at",
            ]
        )

        # 2) Продлеваем/активируем подписку по плану из БД
        if not payment.plan:
            raise ValueError(f"Payment {payment.id} has no plan связанный с оплатой")

        plan: SubscriptionPlan = payment.plan

        if plan.code == "FREE" or plan.price <= 0:
            # Такое не должно происходить, но на всякий случай не ломаем систему
            logger.warning(
                f"[payment.succeeded] paid payment has FREE/zero plan: payment_id={payment.id}, plan={plan.code}"
            )
            return

        # Берём длительность из плана (SSOT)
        duration_days = int(plan.duration_days or 0)
        if duration_days <= 0:
            raise ValueError(f"Plan {plan.code} has invalid duration_days={plan.duration_days}")

        subscription = activate_or_extend_subscription(
            user=payment.user,
            plan_code=plan.code,
            duration_days=duration_days,
        )

        # 3) Если мы сохраняли карту — обновляем данные карты в Subscription
        # и разрешаем автопродление (бизнес-решение: успешная оплата с сохранением карты = можно renew)
        if payment.save_payment_method and payment_method_id:
            subscription.yookassa_payment_method_id = payment_method_id
            subscription.card_mask = card_mask
            subscription.card_brand = card_brand

            # Автопродление включаем только если подписка не FREE и есть payment_method
            if subscription.plan.code != "FREE":
                subscription.auto_renew = True

            subscription.save(
                update_fields=[
                    "yookassa_payment_method_id",
                    "card_mask",
                    "card_brand",
                    "auto_renew",
                    "updated_at",
                ]
            )

        # 4) Кэш плана пользователя — в ноль
        invalidate_user_plan_cache(payment.user_id)

        # 5) Отправляем уведомление админам о новой PRO подписке
        # Уведомление отправляется только для платных планов (не FREE)
        if plan.code != "FREE" and plan.price > 0:
            try:
                send_pro_subscription_notification(
                    subscription=subscription,
                    plan=plan,
                )
            except Exception as notify_err:
                # Ошибка уведомления не должна ломать основной процесс
                logger.warning(
                    f"[payment.succeeded] Не удалось отправить уведомление: {notify_err}"
                )

        logger.info(
            f"[payment.succeeded] ok: payment_id={payment.id}, yk_id={yk_payment_id}, "
            f"user_id={payment.user_id}, plan={plan.code}, duration_days={duration_days}"
        )


def _handle_payment_canceled(payload: Dict[str, Any]) -> None:
    """
    payment.canceled:
    - находим Payment
    - если уже SUCCEEDED/REFUNDED — не трогаем
    - иначе помечаем CANCELED + webhook_processed_at
    """
    obj = payload.get("object") or {}
    yk_payment_id = obj.get("id")
    if not yk_payment_id:
        raise ValueError("payment.canceled payload has no object.id")

    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(yookassa_payment_id=yk_payment_id)

        if payment.status in {"SUCCEEDED", "REFUNDED"}:
            logger.info(
                f"[payment.canceled] ignored: status={payment.status}, payment_id={payment.id}"
            )
            return

        if payment.status == "CANCELED":
            logger.info(f"[payment.canceled] already processed: payment_id={payment.id}")
            return

        payment.status = "CANCELED"
        payment.webhook_processed_at = timezone.now()
        payment.save(update_fields=["status", "webhook_processed_at", "updated_at"])

        logger.info(
            f"[payment.canceled] ok: payment_id={payment.id}, yk_id={yk_payment_id}"
        )


def _handle_payment_waiting_for_capture(payload: Dict[str, Any]) -> None:
    """
    payment.waiting_for_capture:
    - для нашего сценария обычно редкость (у нас capture=True),
      но на всякий случай поддерживаем:
    - помечаем WAITING_FOR_CAPTURE, если платёж ещё не финализирован
    """
    obj = payload.get("object") or {}
    yk_payment_id = obj.get("id")
    if not yk_payment_id:
        raise ValueError("payment.waiting_for_capture payload has no object.id")

    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(yookassa_payment_id=yk_payment_id)

        # Если уже финализирован — не трогаем
        if payment.status in {"SUCCEEDED", "CANCELED", "FAILED", "REFUNDED"}:
            logger.info(
                f"[payment.waiting_for_capture] ignored: status={payment.status}, payment_id={payment.id}"
            )
            return

        if payment.status == "WAITING_FOR_CAPTURE":
            logger.info(f"[payment.waiting_for_capture] already set: payment_id={payment.id}")
            return

        payment.status = "WAITING_FOR_CAPTURE"
        payment.save(update_fields=["status", "updated_at"])

        logger.info(
            f"[payment.waiting_for_capture] ok: payment_id={payment.id}, yk_id={yk_payment_id}"
        )


def _handle_refund_succeeded(payload: Dict[str, Any]) -> None:
    """
    refund.succeeded:
    - создаём/обновляем Refund запись
    - помечаем исходный Payment как REFUNDED (если он найден)
    - подписку в FREE автоматически НЕ переводим (это бизнес-решение).
      Если тебе нужно — можно добавить правило: refund полного платежа -> откат подписки.
    """
    obj = payload.get("object") or {}
    yk_refund_id = obj.get("id")
    yk_payment_id = obj.get("payment_id")

    if not yk_refund_id or not yk_payment_id:
        raise ValueError("refund.succeeded payload has no object.id or object.payment_id")

    amount_value = None
    try:
        amount_value = obj.get("amount", {}).get("value")
    except Exception:
        amount_value = None

    with transaction.atomic():
        payment = Payment.objects.select_for_update().filter(yookassa_payment_id=yk_payment_id).first()

        # 1) Refund запись (для админки/учёта)
        refund, created = Refund.objects.get_or_create(
            yookassa_refund_id=yk_refund_id,
            defaults={
                "payment": payment if payment else None,  # может быть None, если не нашли payment
                "amount": amount_value or 0,
                "status": "SUCCEEDED",
                "reason": "",
                "error_message": "",
                "completed_at": timezone.now(),
            },
        )

        if not created:
            # если уже есть — просто обновим статус/дату
            refund.status = "SUCCEEDED"
            refund.completed_at = timezone.now()
            refund.save(update_fields=["status", "completed_at", "updated_at"])

        # 2) Payment -> REFUNDED (если нашли payment)
        if payment:
            if payment.status == "REFUNDED":
                logger.info(f"[refund.succeeded] already processed: payment_id={payment.id}")
                return

            payment.status = "REFUNDED"
            payment.webhook_processed_at = timezone.now()
            payment.save(update_fields=["status", "webhook_processed_at", "updated_at"])

            logger.info(
                f"[refund.succeeded] ok: refund_id={yk_refund_id}, payment_id={payment.id}, yk_payment_id={yk_payment_id}"
            )
        else:
            logger.warning(
                f"[refund.succeeded] payment not found in DB: yk_payment_id={yk_payment_id}, refund_id={yk_refund_id}"
            )


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _extract_payment_method_info(obj: Dict[str, Any]) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Аккуратно вытаскиваем payment_method данные из payload.
    Возвращаем:
      (payment_method_id, card_mask, card_brand)

    Примечание:
    - YooKassa может прислать payment_method не всегда.
    - card last4 и brand могут быть внутри payment_method.card.
    """
    payment_method = obj.get("payment_method") or {}
    payment_method_id = payment_method.get("id")

    card = payment_method.get("card") or {}
    last4 = card.get("last4")
    brand = card.get("card_type") or card.get("issuer_country")  # brand зависит от формата YooKassa

    card_mask = f"•••• {last4}" if last4 else None
    card_brand = brand if brand else None

    return payment_method_id, card_mask, card_brand
