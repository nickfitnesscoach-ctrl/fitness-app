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

from apps.billing.models import Payment, Refund, Subscription, SubscriptionPlan
from apps.billing.notifications import send_pro_subscription_notification
from apps.billing.services import activate_or_extend_subscription, invalidate_user_plan_cache

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Публичная точка входа для views.py
# ---------------------------------------------------------------------


def handle_yookassa_event(
    *, event_type: str, payload: Dict[str, Any], trace_id: str = None
) -> None:
    """
    Главный роутер событий.

    Args:
        event_type: Тип события от YooKassa
        payload: Полный payload webhook'а
        trace_id: ID трейса для корреляции логов

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
        logger.info("[WEBHOOK_UNHANDLED] trace_id=%s event_type=%s", trace_id, event_type)
        return

    handler(payload, trace_id=trace_id)


# ---------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------


def _handle_payment_succeeded(payload: Dict[str, Any], *, trace_id: str = None) -> None:
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
        # CRITICAL SAFETY: Use helper function to avoid FOR UPDATE + OUTER JOIN crash
        # See: lock_payment_by_yookassa_id() docstring and production incident 2026-01-14
        payment = lock_payment_by_yookassa_id(yk_payment_id)

        # Идемпотентность по внутреннему статусу:
        # если уже успешно обработан — выходим без ошибок
        if payment.status == "SUCCEEDED":
            logger.info(
                "[payment.succeeded] already processed: payment_id=%s, trace_id=%s",
                payment.id,
                trace_id,
            )
            return

        # Если по каким-то причинам уже REFUNDED/CANCELED — тоже не ломаемся
        if payment.status in {"REFUNDED", "CANCELED", "FAILED"}:
            logger.warning(
                "[payment.succeeded] ignored due to status=%s: payment_id=%s, yk_id=%s, trace_id=%s",
                payment.status,
                payment.id,
                yk_payment_id,
                trace_id,
            )
            return

        # P0-A: Достаём payment_method с проверкой payment_method.saved
        payment_method_id, card_mask, card_brand, payment_method_saved = (
            _extract_payment_method_info(obj)
        )

        # 1) Помечаем платёж успешным
        payment.status = "SUCCEEDED"
        payment.paid_at = timezone.now()
        payment.webhook_processed_at = timezone.now()

        # P0-A: Сохраняем payment_method_id в Payment только если saved=True
        if payment.save_payment_method and payment_method_id and payment_method_saved:
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
                "[payment.succeeded] paid payment has FREE/zero plan: payment_id=%s, plan=%s, trace_id=%s",
                payment.id,
                plan.code,
                trace_id,
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

        # P0-A: Если это НЕ recurring платёж и карта сохранена — обновляем Subscription
        # Для recurring платежей мы НЕ обновляем payment_method (он уже сохранён)
        if (
            not payment.is_recurring
            and payment.save_payment_method
            and payment_method_id
            and payment_method_saved
        ):
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

            logger.info(
                "[payment.succeeded] Saved payment method: sub_id=%s, card_mask=%s, card_brand=%s, trace_id=%s",
                subscription.id,
                card_mask,
                card_brand,
                trace_id,
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
                    "[payment.succeeded] Не удалось отправить уведомление: %s, trace_id=%s",
                    notify_err,
                    trace_id,
                )

        logger.info(
            "[payment.succeeded] ok: payment_id=%s, yk_id=%s, user_id=%s, plan=%s, "
            "duration_days=%s, is_recurring=%s, trace_id=%s",
            payment.id,
            yk_payment_id,
            payment.user_id,
            plan.code,
            duration_days,
            payment.is_recurring,
            trace_id,
        )


def _handle_payment_canceled(payload: Dict[str, Any], *, trace_id: str = None) -> None:
    """
    payment.canceled:
    - находим Payment
    - если уже SUCCEEDED/REFUNDED — не трогаем
    - иначе помечаем CANCELED + webhook_processed_at
    - P0-C: для recurring платежей обрабатываем cancellation_details.reason
    """
    obj = payload.get("object") or {}
    yk_payment_id = obj.get("id")
    if not yk_payment_id:
        raise ValueError("payment.canceled payload has no object.id")

    with transaction.atomic():
        # CRITICAL SAFETY: Use helper function to avoid FOR UPDATE + OUTER JOIN crash
        # See: lock_payment_by_yookassa_id() docstring and production incident 2026-01-14
        payment = lock_payment_by_yookassa_id(yk_payment_id)

        if payment.status in {"SUCCEEDED", "REFUNDED"}:
            logger.info(
                "[payment.canceled] ignored: status=%s, payment_id=%s, trace_id=%s",
                payment.status,
                payment.id,
                trace_id,
            )
            return

        if payment.status == "CANCELED":
            logger.info(
                "[payment.canceled] already processed: payment_id=%s, trace_id=%s",
                payment.id,
                trace_id,
            )
            return

        # P0-C: Извлекаем cancellation_details для recurring платежей
        cancellation_details = obj.get("cancellation_details") or {}
        cancellation_reason = cancellation_details.get("reason")

        payment.status = "CANCELED"
        payment.webhook_processed_at = timezone.now()

        # Сохраняем причину отмены в error_message для отладки
        if cancellation_reason:
            payment.error_message = f"Cancellation reason: {cancellation_reason}"

        payment.save(
            update_fields=["status", "webhook_processed_at", "error_message", "updated_at"]
        )

        # P0-C: Обрабатываем cancellation для recurring платежей
        if payment.is_recurring and payment.subscription and cancellation_reason:
            _handle_recurring_cancellation(
                subscription=payment.subscription,
                cancellation_reason=cancellation_reason,
                trace_id=trace_id,
            )

        logger.info(
            "[payment.canceled] ok: payment_id=%s, yk_id=%s, is_recurring=%s, reason=%s, trace_id=%s",
            payment.id,
            yk_payment_id,
            payment.is_recurring,
            cancellation_reason,
            trace_id,
        )


def _handle_payment_waiting_for_capture(payload: Dict[str, Any], *, trace_id: str = None) -> None:
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
        # CRITICAL SAFETY: Use helper function to avoid FOR UPDATE + OUTER JOIN crash
        # See: lock_payment_by_yookassa_id() docstring and production incident 2026-01-14
        payment = lock_payment_by_yookassa_id(yk_payment_id)

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


def _handle_refund_succeeded(payload: Dict[str, Any], *, trace_id: str = None) -> None:
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
        # CRITICAL SAFETY: Use helper function to avoid FOR UPDATE + OUTER JOIN crash
        # Using optional variant because refund webhook may arrive before payment webhook
        # See: lock_payment_by_yookassa_id_optional() docstring and production incident 2026-01-14
        payment = lock_payment_by_yookassa_id_optional(yk_payment_id)

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


def lock_payment_by_yookassa_id(yookassa_payment_id: str) -> Payment:
    """
    Safely lock Payment by YooKassa ID without causing PostgreSQL FOR UPDATE errors.

    CRITICAL SAFETY: This function does NOT use select_related() to avoid the PostgreSQL error:
    "FOR UPDATE cannot be applied to the nullable side of an outer join"

    Payment model FK constraints:
    - user: NOT NULL → can be fetched separately after lock if needed
    - plan: nullable → MUST access via lazy loading (payment.plan)
    - subscription: nullable → MUST access via lazy loading (payment.subscription)

    Lock strategy:
    - Lock ONLY the base Payment table (no JOINs)
    - Access related objects AFTER lock is acquired via lazy loading
    - Lazy loading is safe because it happens within the same transaction

    Args:
        yookassa_payment_id: YooKassa payment UUID

    Returns:
        Locked Payment instance

    Raises:
        Payment.DoesNotExist: If payment not found

    Example:
        with transaction.atomic():
            payment = lock_payment_by_yookassa_id("30f8c80c-000f-5000-b000-175b519519f5")
            # Access subscription AFTER lock (separate query within transaction)
            if payment.subscription_id:
                subscription = payment.subscription

    See: production incident 2026-01-14 (payment.canceled crash)
    """
    return Payment.objects.select_for_update().get(yookassa_payment_id=yookassa_payment_id)


def lock_payment_by_yookassa_id_optional(yookassa_payment_id: str) -> Optional[Payment]:
    """
    Safely lock Payment by YooKassa ID (returns None if not found).

    Used in refund.succeeded handler where payment may not exist yet
    (refund webhook can arrive before payment webhook in rare cases).

    CRITICAL SAFETY: Same as lock_payment_by_yookassa_id() but uses .first() instead of .get()

    Args:
        yookassa_payment_id: YooKassa payment UUID

    Returns:
        Locked Payment instance or None if not found

    Example:
        with transaction.atomic():
            payment = lock_payment_by_yookassa_id_optional("30f8c80c-000f-5000-b000-175b519519f5")
            if payment:
                payment.status = "REFUNDED"
                payment.save()

    See: production incident 2026-01-14 (payment.canceled crash)
    """
    return Payment.objects.select_for_update().filter(yookassa_payment_id=yookassa_payment_id).first()


def _handle_recurring_cancellation(
    *, subscription: "Subscription", cancellation_reason: str, trace_id: str = None
) -> None:
    """
    P0-C: Обрабатываем отмену recurring платежа в зависимости от причины.

    Reasons from YooKassa API:
    - "permission_revoked" — пользователь отозвал разрешение на списание
    - "card_expired" — карта истекла
    - "insufficient_funds" — недостаточно средств (временная проблема)
    - "3d_secure_failed" — не прошла 3DS аутентификация
    - "call_issuer" — нужно связаться с банком
    - "canceled_by_merchant" — отменено мерчантом
    - "general_decline" — общий отказ банка

    Бизнес-логика:
    - permission_revoked, card_expired → выключаем auto_renew, очищаем payment_method
    - insufficient_funds → НЕ выключаем auto_renew (разрешаем retry через 24h)
    - остальные → НЕ выключаем auto_renew (могут быть временными)
    """
    PERMANENT_FAILURE_REASONS = {"permission_revoked", "card_expired"}

    if cancellation_reason in PERMANENT_FAILURE_REASONS:
        # Permanent failure — выключаем auto_renew и очищаем payment_method
        subscription.auto_renew = False
        subscription.yookassa_payment_method_id = None
        subscription.card_mask = None
        subscription.card_brand = None
        subscription.save(
            update_fields=[
                "auto_renew",
                "yookassa_payment_method_id",
                "card_mask",
                "card_brand",
                "updated_at",
            ]
        )

        logger.warning(
            "[RECURRING_CANCEL] Auto-renew disabled due to permanent failure: "
            "sub_id=%s, reason=%s, trace_id=%s",
            subscription.id,
            cancellation_reason,
            trace_id,
        )
    elif cancellation_reason == "insufficient_funds":
        # Temporary failure — разрешаем retry, не выключаем auto_renew
        logger.info(
            "[RECURRING_CANCEL] Insufficient funds (will retry): "
            "sub_id=%s, reason=%s, trace_id=%s",
            subscription.id,
            cancellation_reason,
            trace_id,
        )
    else:
        # Другие причины — тоже не выключаем auto_renew (могут быть временными)
        logger.info(
            "[RECURRING_CANCEL] Recurring payment failed (will retry): "
            "sub_id=%s, reason=%s, trace_id=%s",
            subscription.id,
            cancellation_reason,
            trace_id,
        )


def _extract_payment_method_info(
    obj: Dict[str, Any],
) -> tuple[Optional[str], Optional[str], Optional[str], bool]:
    """
    Аккуратно вытаскиваем payment_method данные из payload.
    Возвращаем:
      (payment_method_id, card_mask, card_brand, saved)

    Примечание:
    - YooKassa может прислать payment_method не всегда.
    - card last4 и brand могут быть внутри payment_method.card.
    - saved=True означает, что карта сохранена для рекуррентных платежей (P0-A)
    """
    payment_method = obj.get("payment_method") or {}
    payment_method_id = payment_method.get("id")
    payment_method_saved = payment_method.get("saved", False)

    card = payment_method.get("card") or {}
    last4 = card.get("last4")
    brand = card.get("card_type") or card.get("issuer_country")  # brand зависит от формата YooKassa

    card_mask = f"•••• {last4}" if last4 else None
    card_brand = brand if brand else None

    return payment_method_id, card_mask, card_brand, payment_method_saved
