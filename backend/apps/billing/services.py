"""
billing/services.py

Сервисы (бизнес-слой) для биллинга EatFit24.

Зачем этот файл:
- держать "ядро" бизнес-логики отдельно от views/webhooks
- сделать один понятный источник истины по:
  1) созданию платежей
  2) продлению подписки
  3) определению текущего плана (с кешем)

Ключевые принципы безопасности:
- фронт НЕ передает сумму, дни, фичи — только plan_code
- цена/длительность/лимиты берутся из SubscriptionPlan (БД)
- подписка считается оплаченной ТОЛЬКО после webhook (webhooks/handlers.py)

Важно про YooKassa:
- Здесь используется официальный SDK (yookassa)
- SDK хранит креды в глобальном Configuration, поэтому мы конфигурируем
  аккуратно, и избегаем лишнего логирования секретов.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
import logging
from typing import Any, Dict, Optional, Tuple
import uuid

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils import timezone
from yookassa import Configuration, Payment as YooKassaPayment
from yookassa.domain.notification import WebhookNotificationFactory

from .models import Payment, Subscription, SubscriptionPlan

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# YooKassa payload builder
# ---------------------------------------------------------------------

def build_yookassa_payment_payload(
    *,
    amount: Decimal,
    description: str,
    return_url: str,
    save_payment_method: bool = True,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Универсальный билдер payload для YooKassa.

    Режимы работы:
    - BILLING_RECURRING_ENABLED=true → recurring mode (save_payment_method)
    - BILLING_RECURRING_ENABLED=false → one-time mode (без recurring полей)

    Это единственное место, где определяется структура payload.
    """
    recurring_enabled = getattr(settings, "BILLING_RECURRING_ENABLED", False)

    # Базовые поля (обязательны всегда)
    payload: Dict[str, Any] = {
        "amount": {"value": str(amount), "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": return_url},
        "capture": True,
        "description": description,
        "metadata": metadata or {},
    }

    # Добавляем billing_mode в metadata для прозрачности
    billing_mode = "RECURRING" if recurring_enabled else "ONE_TIME"
    payload["metadata"]["billing_mode"] = billing_mode

    # Если recurring включён И запрошено сохранение карты
    if recurring_enabled and save_payment_method:
        payload["save_payment_method"] = True

    logger.info(
        "Built YooKassa payload: mode=%s, save_payment_method=%s, amount=%s",
        billing_mode,
        save_payment_method if recurring_enabled else False,
        amount,
    )

    return payload


# ---------------------------------------------------------------------
# YooKassa SDK wrapper
# ---------------------------------------------------------------------

class YooKassaService:
    """
    Тонкая обертка над YooKassa SDK.

    Почему так:
    - SDK использует глобальный Configuration
    - мы валидируем креды и конфигурируем их "явно"
    """

    def __init__(self) -> None:
        self.shop_id = getattr(settings, "YOOKASSA_SHOP_ID", None)
        self.secret_key = getattr(settings, "YOOKASSA_SECRET_KEY", None)

        if not self.shop_id or not self.secret_key:
            raise ImproperlyConfigured(
                "YooKassa credentials not configured. "
                "Set YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY env vars."
            )

        # shop_id обычно числовой
        if not str(self.shop_id).isdigit():
            raise ImproperlyConfigured(
                f"Invalid YOOKASSA_SHOP_ID format: {self.shop_id}. Must be numeric."
            )

        # секрет обычно начинается с test_/live_
        if not (str(self.secret_key).startswith("test_") or str(self.secret_key).startswith("live_")):
            raise ImproperlyConfigured(
                "Invalid YOOKASSA_SECRET_KEY format. Must start with 'test_' or 'live_'."
            )

        if str(self.secret_key).startswith(("test_your", "live_your")):
            raise ImproperlyConfigured(
                "YOOKASSA_SECRET_KEY looks like placeholder. Replace with real key."
            )

        # Конфигурируем SDK
        self._configure()

        logger.info(
            "YooKassa service initialized. shop_id=%s, env=%s",
            self.shop_id,
            "TEST" if str(self.secret_key).startswith("test_") else "PROD",
        )

    def _configure(self) -> None:
        """
        Конфиг SDK (глобальный, к сожалению).
        """
        Configuration.account_id = str(self.shop_id)
        Configuration.secret_key = str(self.secret_key)

    def create_payment(
        self,
        *,
        amount: Decimal,
        description: str,
        return_url: str,
        save_payment_method: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Создать платеж в YooKassa.

        Возвращает нормализованный dict с тем, что нужно приложению.
        """
        idempotence_key = str(uuid.uuid4())

        # Используем централизованный билдер payload
        payload = build_yookassa_payment_payload(
            amount=amount,
            description=description,
            return_url=return_url,
            save_payment_method=save_payment_method,
            metadata=metadata,
        )

        try:
            payment = YooKassaPayment.create(payload, idempotence_key)

            return {
                "id": payment.id,
                "status": payment.status,
                "amount": payment.amount.value,
                "currency": payment.amount.currency,
                "confirmation_url": payment.confirmation.confirmation_url,
                "payment_method_id": getattr(payment.payment_method, "id", None) if payment.payment_method else None,
            }
        except Exception as e:
            # Секреты не логируем. Достаточно текста исключения.
            logger.error("YooKassa create_payment error: %s", str(e), exc_info=True)
            raise

    def create_recurring_payment(
        self,
        *,
        amount: Decimal,
        description: str,
        payment_method_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Создать рекуррентный платеж по сохраненному payment_method_id.
        """
        idempotence_key = str(uuid.uuid4())

        payload: Dict[str, Any] = {
            "amount": {"value": str(amount), "currency": "RUB"},
            "capture": True,
            "payment_method_id": payment_method_id,
            "description": description,
            "metadata": metadata or {},
        }

        try:
            payment = YooKassaPayment.create(payload, idempotence_key)
            return {
                "id": payment.id,
                "status": payment.status,
                "amount": payment.amount.value,
                "currency": payment.amount.currency,
                "payment_method_id": payment_method_id,
            }
        except Exception as e:
            logger.error("YooKassa create_recurring_payment error: %s", str(e), exc_info=True)
            raise

    def get_payment_info(self, *, payment_id: str) -> Dict[str, Any]:
        """
        Получить информацию по платежу.
        """
        try:
            payment = YooKassaPayment.find_one(payment_id)
            return {
                "id": payment.id,
                "status": payment.status,
                "amount": payment.amount.value,
                "currency": payment.amount.currency,
                "payment_method_id": getattr(payment.payment_method, "id", None) if payment.payment_method else None,
                "paid": payment.paid,
                "created_at": payment.created_at,
            }
        except Exception as e:
            logger.error("YooKassa get_payment_info error: %s", str(e), exc_info=True)
            raise

    @staticmethod
    def parse_webhook_notification(request_body: Dict[str, Any]):
        """
        Парсинг webhook (если где-то нужно как объект).
        Обычно мы работаем напрямую с payload, но оставляем метод для совместимости.
        """
        return WebhookNotificationFactory().create(request_body)


# ---------------------------------------------------------------------
# План/подписка: источник истины
# ---------------------------------------------------------------------

def _get_free_plan() -> SubscriptionPlan:
    """
    FREE план — фундамент.
    Ищем сначала по code=FREE, затем legacy name=FREE.
    """
    try:
        return SubscriptionPlan.objects.get(code="FREE", is_active=True)
    except SubscriptionPlan.DoesNotExist:
        try:
            return SubscriptionPlan.objects.get(name="FREE", is_active=True)
        except SubscriptionPlan.DoesNotExist:
            # Не создаём автоматически молча — это скрытая магия.
            # Пусть админ явно создаст план.
            raise ValueError("FREE plan not found. Create it in Django Admin (code=FREE, price=0).")


def get_plan_by_code_or_legacy(plan_code: str) -> SubscriptionPlan:
    """
    Ищем план по новому полю code, и fallback по legacy name.
    """
    try:
        return SubscriptionPlan.objects.get(code=plan_code, is_active=True)
    except SubscriptionPlan.DoesNotExist:
        try:
            plan = SubscriptionPlan.objects.get(name=plan_code, is_active=True)
            logger.warning("Plan found by legacy name='%s'. Prefer code.", plan_code)
            return plan
        except SubscriptionPlan.DoesNotExist:
            raise ValueError(f"Plan '{plan_code}' not found or inactive")


def ensure_subscription_exists(user) -> Subscription:
    """
    Гарантируем, что у пользователя есть Subscription.

    Да, у тебя есть сигнал post_save(User)->create_free_subscription,
    но здесь мы делаем "страховку", чтобы API/команды не падали.
    """
    free_plan = _get_free_plan()

    sub, _ = Subscription.objects.get_or_create(
        user=user,
        defaults={
            "plan": free_plan,
            "start_date": timezone.now(),
            # FREE может быть "вечным" по бизнес-логике — end_date не критичен для FREE,
            # потому что FREE считается неистекающим в Subscription.is_expired().
            "end_date": timezone.now() + timedelta(days=365 * 10),
            "is_active": True,
            "auto_renew": False,
        },
    )
    return sub


# ---------------------------------------------------------------------
# Создание платежа (локальная запись + YooKassa)
# ---------------------------------------------------------------------

def create_subscription_payment(
    *,
    user,
    plan_code: str,
    return_url: Optional[str] = None,
    save_payment_method: bool = True,
) -> Tuple[Payment, str]:
    """
    Универсальный сервис создания платежа подписки.

    Возвращает:
      (payment_obj, confirmation_url)

    Ошибки:
      ValueError — невалидный plan_code или FREE
      Exception — проблемы с YooKassa/БД
    """
    plan = get_plan_by_code_or_legacy(plan_code)

    if plan.price <= 0:
        raise ValueError("Cannot create payment for FREE plan")

    resolved_return_url = return_url or getattr(settings, "YOOKASSA_RETURN_URL", None)
    if not resolved_return_url:
        raise ValueError("return_url is required (provide it or set settings.YOOKASSA_RETURN_URL)")

    with transaction.atomic():
        subscription = ensure_subscription_exists(user)

        payment = Payment.objects.create(
            user=user,
            subscription=subscription,
            plan=plan,
            amount=plan.price,
            currency="RUB",
            status="PENDING",
            provider="YOOKASSA",
            description=f"Подписка {plan.display_name}",
            save_payment_method=save_payment_method,
            is_recurring=False,
        )

        yk = YooKassaService()
        yk_payment = yk.create_payment(
            amount=plan.price,
            description=payment.description,
            return_url=resolved_return_url,
            save_payment_method=save_payment_method,
            metadata={
                "payment_id": str(payment.id),
                "user_id": str(user.id),
                "plan_code": plan.code,
            },
        )

        payment.yookassa_payment_id = yk_payment["id"]

        # Получаем billing_mode из настроек для согласованности
        recurring_enabled = getattr(settings, "BILLING_RECURRING_ENABLED", False)
        billing_mode = "RECURRING" if recurring_enabled else "ONE_TIME"

        payment.metadata = {
            "idempotence_note": "SDK handles idempotence_key per request",
            "plan_code": plan.code,
            "amount": str(plan.price),
            "return_url": resolved_return_url,
            "billing_mode": billing_mode,
        }
        payment.save(update_fields=["yookassa_payment_id", "metadata", "updated_at"])

    confirmation_url = yk_payment["confirmation_url"]
    logger.info(
        "Payment created: payment_id=%s, yk_id=%s, user_id=%s, plan=%s",
        payment.id,
        payment.yookassa_payment_id,
        user.id,
        plan.code,
    )
    return payment, confirmation_url


def create_monthly_subscription_payment(*, user, return_url: Optional[str] = None) -> Tuple[Payment, str]:
    """
    Legacy helper.
    Раньше был MONTHLY, сейчас рекомендуется PRO_MONTHLY.
    Оставляем для совместимости.
    """
    return create_subscription_payment(user=user, plan_code="MONTHLY", return_url=return_url, save_payment_method=True)


# ---------------------------------------------------------------------
# Активация / продление подписки
# ---------------------------------------------------------------------

def activate_or_extend_subscription(*, user, plan_code: str, duration_days: int) -> Subscription:
    """
    Активирует или продлевает подписку.

    Логика:
    - если подписки нет — создаём
    - если истекла — стартуем от сейчас
    - если активна — добавляем дни к end_date
    - обновляем plan на тот, который оплачен
    - инвалидируем кеш плана пользователя
    """
    if duration_days <= 0:
        raise ValueError(f"duration_days must be > 0, got {duration_days}")

    plan = get_plan_by_code_or_legacy(plan_code)

    with transaction.atomic():
        sub = ensure_subscription_exists(user)

        now = timezone.now()

        # Если FREE — просто переключаемся на платный
        if sub.plan.code == "FREE":
            sub.start_date = now
            sub.end_date = now + timedelta(days=duration_days)
        else:
            # Не FREE: проверяем истечение
            if sub.is_expired():
                sub.start_date = now
                sub.end_date = now + timedelta(days=duration_days)
            else:
                sub.end_date = sub.end_date + timedelta(days=duration_days)

        sub.plan = plan
        sub.is_active = True
        sub.save(update_fields=["plan", "start_date", "end_date", "is_active", "updated_at"])

    invalidate_user_plan_cache(user.id)

    logger.info(
        "Subscription activated/extended: user_id=%s, plan=%s, end_date=%s",
        user.id,
        plan.code,
        sub.end_date,
    )
    return sub


# ---------------------------------------------------------------------
# Определение действующего плана (с кешем)
# ---------------------------------------------------------------------

def invalidate_user_plan_cache(user_id: int) -> None:
    """
    Инвалидируем кеш плана пользователя.
    Вызываем после любых изменений подписки.
    """
    cache_key = f"user_plan:{user_id}"
    cache.delete(cache_key)
    logger.debug("Invalidated plan cache: user_id=%s", user_id)


def get_effective_plan_for_user(user) -> SubscriptionPlan:
    """
    Действующий план для пользователя:

    - если есть Subscription и она активна и не истекла → её plan
    - иначе FREE

    Кеш:
    - 5 минут по plan.id
    """
    cache_key = f"user_plan:{user.id}"
    cached_plan_id = cache.get(cache_key)

    if cached_plan_id is not None:
        try:
            return SubscriptionPlan.objects.get(id=cached_plan_id)
        except SubscriptionPlan.DoesNotExist:
            cache.delete(cache_key)

    plan = _get_effective_plan_uncached(user)
    cache.set(cache_key, plan.id, timeout=300)
    return plan


def _get_effective_plan_uncached(user) -> SubscriptionPlan:
    """
    Внутренняя версия без кеша.
    """
    try:
        sub = Subscription.objects.select_related("plan").get(user=user)
        if sub.is_active and not sub.is_expired():
            return sub.plan
    except Subscription.DoesNotExist:
        pass

    return _get_free_plan()
