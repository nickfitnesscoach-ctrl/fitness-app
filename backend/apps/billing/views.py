"""
billing/views.py

Billing API Views (DRF function-based).

Задачи файла:
- Дать фронту стабильный API для: планов, статуса подписки, оплаты, привязки карты, истории платежей
- Свести логику к понятному "ядру" без дублирования

Принципы безопасности:
- Никогда не принимаем сумму/цену с фронта — только plan_code
- Все цены/длительности/лимиты берём только из БД (SubscriptionPlan)
- Подписка активируется/продлевается ТОЛЬКО после webhook (см. billing/webhooks/*)
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
import logging
from typing import Tuple

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from yookassa.domain.exceptions import (
    ApiError,
    BadRequestError,
    ForbiddenError,
    UnauthorizedError,
)

from apps.common.audit import SecurityAuditLogger

from .models import Payment, Subscription, SubscriptionPlan
from .serializers import (
    AutoRenewToggleSerializer,
    SubscriptionPlanPublicSerializer,
)
from .services import YooKassaService
from .throttles import (
    BillingPollingThrottle,  # [SECURITY] Rate limiting для polling
    PaymentCreationThrottle,  # [SECURITY] Rate limiting для платежей
)

logger = logging.getLogger(__name__)


# =====================================================================
# Helpers (unified errors + safe plan/subscription access)
# =====================================================================

def _err(code: str, message: str, http_status: int):
    """Единый формат ошибок для billing (чтобы фронт не гадал)."""
    return Response({"error": {"code": code, "message": message}}, status=http_status)


def _get_free_plan() -> SubscriptionPlan:
    """
    Получаем FREE план максимально надёжно.

    SSOT = code, но поддерживаем legacy name на всякий случай.
    """
    try:
        return SubscriptionPlan.objects.get(code="FREE", is_active=True)
    except SubscriptionPlan.DoesNotExist:
        try:
            return SubscriptionPlan.objects.get(name="FREE", is_active=True)
        except SubscriptionPlan.DoesNotExist as e:
            raise RuntimeError(
                "FREE plan не найден. Создай план в админке: code=FREE, price=0."
            ) from e


def _get_plan_by_code_or_legacy(plan_code: str) -> SubscriptionPlan:
    """
    Ищем план:
    1) по code (новая логика)
    2) fallback по legacy name (старые клиенты/старый фронт)
    """
    try:
        return SubscriptionPlan.objects.get(code=plan_code, is_active=True)
    except SubscriptionPlan.DoesNotExist:
        try:
            plan = SubscriptionPlan.objects.get(name=plan_code, is_active=True)
            logger.warning(f"Plan found by legacy name='{plan_code}'. Prefer using code.")
            return plan
        except SubscriptionPlan.DoesNotExist as e:
            raise e


def _free_end_date() -> timezone.datetime:
    """
    Что писать в end_date для FREE подписки.

    Важно:
    - FREE по бизнес-логике "не истекает" (или истекает очень нескоро)
    - но поле end_date нужно, чтобы:
      - не ломались проверки is_expired()
      - не было путаницы в админке
      - не падали выборки/индексы/вьюхи
    """
    if hasattr(settings, "FREE_SUBSCRIPTION_END_DATE") and settings.FREE_SUBSCRIPTION_END_DATE:
        return settings.FREE_SUBSCRIPTION_END_DATE
    # fallback: 10 лет вперёд
    return timezone.now() + timedelta(days=365 * 10)


def _get_or_create_user_subscription(user) -> Subscription:
    """
    Гарантируем, что у пользователя есть Subscription.

    Да, у тебя есть сигнал create_free_subscription в models.py,
    но на практике безопаснее иметь "страховку" на уровне бизнес-логики:
    - миграции/сигналы могли не отработать
    - пользователь мог быть создан импортом/скриптом
    """
    free_plan = _get_free_plan()
    sub, _ = Subscription.objects.get_or_create(
        user=user,
        defaults={
            "plan": free_plan,
            "start_date": timezone.now(),
            "end_date": _free_end_date(),
            "is_active": True,
            "auto_renew": False,
        },
    )

    # Если подписка есть, но по какой-то причине FREE и end_date "в прошлом" — вылечим
    if sub.plan.code == "FREE" and sub.end_date and sub.end_date <= timezone.now():
        sub.end_date = _free_end_date()
        sub.is_active = True
        sub.save(update_fields=["end_date", "is_active", "updated_at"])

    return sub


def _build_default_return_url(request) -> str:
    """
    Единый дефолтный return_url.

    Приоритет:
    1) settings.YOOKASSA_RETURN_URL (если задан)
    2) собрать от текущего домена (fallback для dev)
    """
    if getattr(settings, "YOOKASSA_RETURN_URL", None):
        return settings.YOOKASSA_RETURN_URL

    base = request.build_absolute_uri("/")
    return base.rstrip("/") + "/payment-success"


def _validate_return_url(url: str | None, request) -> str:
    """
    [SECURITY FIX 2024-12] Валидация return_url для защиты от open redirect.

    Атака: злоумышленник передаёт return_url=https://evil.com/phishing,
    пользователь после оплаты попадает на фишинговый сайт.

    Защита: проверяем домен URL против whitelist (ALLOWED_RETURN_URL_DOMAINS).

    Args:
        url: URL от клиента (может быть None)
        request: Django request (для fallback)

    Returns:
        Безопасный return_url (либо переданный, либо default)
    """
    from urllib.parse import urlparse

    if not url:
        return _build_default_return_url(request)

    try:
        parsed = urlparse(url)
        hostname = parsed.hostname

        if not hostname:
            logger.warning(f"[SECURITY] return_url без hostname: {url}")
            return _build_default_return_url(request)

        allowed_domains = getattr(settings, "ALLOWED_RETURN_URL_DOMAINS", ["eatfit24.ru", "localhost"])

        # Проверяем точное совпадение или субдомен
        is_allowed = any(
            hostname == domain or hostname.endswith(f".{domain}")
            for domain in allowed_domains
        )

        if not is_allowed:
            logger.warning(
                f"[SECURITY] return_url заблокирован (домен не в whitelist): {url}. "
                f"Allowed: {allowed_domains}"
            )
            return _build_default_return_url(request)

        return url

    except Exception as e:
        logger.error(f"[SECURITY] return_url parsing error: {url}, error: {e}")
        return _build_default_return_url(request)


# =====================================================================
# Core: создание платежа (локально + в YooKassa)
# =====================================================================

def _create_subscription_payment_core(
    *,
    user,
    plan_code: str,
    return_url: str,
    save_payment_method: bool,
    description_suffix: str = "",
) -> Tuple[Payment, str]:
    """
    Ядро: создаём локальный Payment + создаём платёж в YooKassa.

    Возвращает: (Payment, confirmation_url)

    Важно:
    - сумма берётся из SubscriptionPlan.price (БД)
    - return_url должен быть уже готовой строкой (core не строит URL, потому что нет request)
    - подписка НЕ активируется здесь (это сделает webhook)
    """
    plan = _get_plan_by_code_or_legacy(plan_code)

    if plan.price <= 0:
        raise ValueError("Cannot create payment for FREE plan")

    if not return_url:
        raise ValueError("return_url is required")

    with transaction.atomic():
        subscription = _get_or_create_user_subscription(user)

        payment = Payment.objects.create(
            user=user,
            subscription=subscription,
            plan=plan,
            amount=plan.price,
            currency="RUB",
            status="PENDING",
            provider="YOOKASSA",
            description=f"Подписка {plan.display_name}{description_suffix}",
            save_payment_method=save_payment_method,
            is_recurring=False,
        )

        yk = YooKassaService()
        yk_payment = yk.create_payment(
            amount=plan.price,
            description=payment.description,
            return_url=return_url,
            save_payment_method=save_payment_method,
            metadata={
                "payment_id": str(payment.id),
                "user_id": str(user.id),
                "plan_code": plan.code,
            },
        )

        payment.yookassa_payment_id = yk_payment["id"]
        payment.save(update_fields=["yookassa_payment_id", "updated_at"])

    return payment, yk_payment["confirmation_url"]


# =====================================================================
# Public endpoints
# =====================================================================

@api_view(["GET"])
@permission_classes([AllowAny])
def get_subscription_plans(request):
    """
    GET /api/v1/billing/plans/
    Публичный список активных планов (кроме тестовых).
    """
    plans = SubscriptionPlan.objects.filter(is_active=True, is_test=False).order_by("price")
    serializer = SubscriptionPlanPublicSerializer(plans, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@throttle_classes([BillingPollingThrottle])  # [SECURITY] 120 req/min для polling
def get_subscription_status(request):
    """
    GET /api/v1/billing/me/
    Короткий статус для UI (план, лимиты, использовано сегодня).
    """
    from .services import get_effective_plan_for_user
    from .usage import DailyUsage

    plan = get_effective_plan_for_user(request.user)

    usage = DailyUsage.objects.get_today(request.user)
    used_today = usage.photo_ai_requests

    if plan.daily_photo_limit is not None:
        remaining_today = max(0, plan.daily_photo_limit - used_today)
    else:
        remaining_today = None

    # Если подписки нет — считаем, что FREE активен
    try:
        sub = request.user.subscription
        is_active = sub.is_active and (not sub.is_expired())
        expires_at = None if plan.code == "FREE" else (sub.end_date.isoformat() if sub.end_date else None)
    except Subscription.DoesNotExist:
        is_active = True
        expires_at = None

    # Кнопка тестового платежа: только админы и только в prod режиме
    telegram_user = getattr(request.user, "telegram_profile", None)
    telegram_admins = getattr(settings, "TELEGRAM_ADMINS", set())
    is_admin = bool(telegram_user and telegram_user.telegram_id in telegram_admins)
    is_prod_mode = getattr(settings, "YOOKASSA_MODE", "") == "prod"
    test_live_payment_available = is_admin and is_prod_mode

    return Response(
        {
            "plan_code": plan.code,
            "plan_name": plan.display_name,
            "expires_at": expires_at,
            "is_active": is_active,
            "daily_photo_limit": plan.daily_photo_limit,
            "used_today": used_today,
            "remaining_today": remaining_today,
            "test_live_payment_available": test_live_payment_available,
        },
        status=status.HTTP_200_OK,
    )


# =====================================================================
# Settings screen endpoints
# =====================================================================

def _build_subscription_details_response(user) -> Response:
    """
    Внутренняя логика для построения ответа с деталями подписки.
    Вынесено для переиспользования в get_subscription_details и set_auto_renew.
    """
    try:
        sub = user.subscription
    except Subscription.DoesNotExist:
        # Нет подписки — возвращаем "как FREE"
        return Response(
            {
                "plan": "free",
                "plan_display": "Free",
                "expires_at": None,
                "is_active": True,
                "autorenew_available": False,
                "autorenew_enabled": False,
                "card_bound": False,
                "payment_method": {"is_attached": False, "card_mask": None, "card_brand": None},
            },
            status=status.HTTP_200_OK,
        )

    is_free = sub.plan.code == "FREE"
    is_active = sub.is_active and (not sub.is_expired())

    # В UI FREE не показываем дату окончания
    expires_at = None if is_free else (sub.end_date.date().isoformat() if sub.end_date else None)

    payment_method_attached = bool(sub.yookassa_payment_method_id)

    return Response(
        {
            "plan": "free" if is_free else "pro",
            "plan_display": "Free" if is_free else "PRO",
            "expires_at": expires_at,
            "is_active": is_active,
            "autorenew_available": (payment_method_attached and not is_free),
            "autorenew_enabled": (bool(sub.auto_renew) if not is_free else False),
            "card_bound": payment_method_attached,
            "payment_method": {
                "is_attached": payment_method_attached,
                "card_mask": sub.card_mask,
                "card_brand": sub.card_brand,
            },
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@throttle_classes([BillingPollingThrottle])  # [SECURITY] 120 req/min для polling
def get_subscription_details(request):
    """
    GET /api/v1/billing/subscription/
    Полная карточка подписки для настроек.
    """
    return _build_subscription_details_response(request.user)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def set_auto_renew(request):
    """
    POST /api/v1/billing/subscription/autorenew/
    Body: { "enabled": true|false }

    Важно:
    - только для платных планов
    - если включаем — должна быть привязана карта (payment_method)
    """
    # Feature flag guard: recurring billing must be enabled
    if not settings.BILLING_RECURRING_ENABLED:
        return Response(
            {
                "error": "Auto-renewal is not available",
                "detail": "Recurring billing is disabled in system configuration"
            },
            status=status.HTTP_409_CONFLICT,
        )

    serializer = AutoRenewToggleSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    enabled = serializer.validated_data["enabled"]

    try:
        sub = request.user.subscription
    except Subscription.DoesNotExist:
        return _err("NO_SUBSCRIPTION", "У вас нет подписки", status.HTTP_404_NOT_FOUND)

    if sub.plan.code == "FREE":
        return _err("NOT_AVAILABLE_FOR_FREE", "Автопродление недоступно для FREE", status.HTTP_400_BAD_REQUEST)

    if enabled and not sub.yookassa_payment_method_id:
        return _err(
            "payment_method_required",
            "Для автопродления нужна привязанная карта. Оформите подписку с сохранением карты.",
            status.HTTP_400_BAD_REQUEST,
        )

    sub.auto_renew = enabled
    sub.save(update_fields=["auto_renew", "updated_at"])

    # FIX: Вызываем внутреннюю функцию вместо view (избегаем AssertionError с DRF Request)
    return _build_subscription_details_response(request.user)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_payment_method_details(request):
    """
    GET /api/v1/billing/payment-method/
    """
    try:
        sub = request.user.subscription
    except Subscription.DoesNotExist:
        return Response(
            {"is_attached": False, "card_mask": None, "card_brand": None},
            status=status.HTTP_200_OK,
        )

    return Response(
        {
            "is_attached": bool(sub.yookassa_payment_method_id),
            "card_mask": sub.card_mask,
            "card_brand": sub.card_brand,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_payments_history(request):
    """
    GET /api/v1/billing/payments/
    Query: ?limit=10

    История платежей (простая, без пагинации страницами).
    """
    limit_raw = request.query_params.get("limit", 10)
    try:
        limit = int(limit_raw)
        limit = max(1, min(limit, 100))
    except (TypeError, ValueError):
        limit = 10

    payments = Payment.objects.filter(user=request.user).order_by("-created_at")[:limit]

    status_map = {
        "PENDING": "pending",
        "WAITING_FOR_CAPTURE": "pending",
        "SUCCEEDED": "succeeded",
        "CANCELED": "canceled",
        "FAILED": "failed",
        "REFUNDED": "refunded",
    }

    results = []
    for p in payments:
        results.append(
            {
                "id": str(p.id),
                "amount": float(p.amount),
                "currency": p.currency,
                "status": status_map.get(p.status, str(p.status).lower()),
                "paid_at": p.paid_at.isoformat() if p.paid_at else None,
                "description": p.description,
            }
        )

    return Response({"results": results}, status=status.HTTP_200_OK)


# =====================================================================
# Payments endpoints
# =====================================================================

@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([PaymentCreationThrottle])  # [SECURITY] 20 req/hour
def create_payment(request):
    """
    POST /api/v1/billing/create-payment/
    Body: { "plan_code": "...", "return_url": "..."? }

    Универсальная точка создания платежа.
    """
    plan_code = request.data.get("plan_code")
    if not plan_code:
        return _err("MISSING_PLAN_CODE", "Укажите plan_code в теле запроса", status.HTTP_400_BAD_REQUEST)

    return_url = _validate_return_url(request.data.get("return_url"), request)

    try:
        payment, confirmation_url = _create_subscription_payment_core(
            user=request.user,
            plan_code=str(plan_code),
            return_url=return_url,
            save_payment_method=True,
        )

        SecurityAuditLogger.log_payment_created(
            user=request.user,
            amount=float(payment.amount),
            plan=str(plan_code),
            request=request,
        )

        return Response(
            {
                "payment_id": str(payment.id),
                "yookassa_payment_id": payment.yookassa_payment_id,
                "confirmation_url": confirmation_url,
            },
            status=status.HTTP_201_CREATED,
        )

    except SubscriptionPlan.DoesNotExist:
        return _err("INVALID_PLAN", f"Plan '{plan_code}' not found or inactive", status.HTTP_400_BAD_REQUEST)
    except ValueError as e:
        return _err("INVALID_PLAN", str(e), status.HTTP_400_BAD_REQUEST)

    # YooKassa-специфичные ошибки
    except ForbiddenError as e:
        # Forbidden обычно означает, что recurring не настроен на аккаунте ЮKassa
        recurring_enabled = getattr(settings, "BILLING_RECURRING_ENABLED", False)

        if recurring_enabled:
            # Если мы пытались использовать recurring, но получили forbidden
            logger.error(
                f"YooKassa Forbidden (recurring mode) for user {request.user.id}: {e}. "
                "Recurring payments may not be enabled on YooKassa account.",
                exc_info=True
            )
            return _err(
                "RECURRING_NOT_AVAILABLE",
                "Автопродление временно недоступно. Попробуйте оплатить без сохранения карты или свяжитесь с поддержкой.",
                status.HTTP_403_FORBIDDEN,
            )
        else:
            # Если recurring выключен, но всё равно forbidden — проблема с магазином/ключами
            logger.error(
                f"YooKassa Forbidden (one-time mode) for user {request.user.id}: {e}. "
                "Check YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY.",
                exc_info=True
            )
            return _err(
                "YOOKASSA_FORBIDDEN",
                "Ошибка доступа к платёжной системе. Свяжитесь с поддержкой.",
                status.HTTP_403_FORBIDDEN,
            )

    except UnauthorizedError as e:
        logger.error(f"YooKassa Unauthorized for user {request.user.id}: {e}. Check credentials.", exc_info=True)
        return _err(
            "YOOKASSA_UNAUTHORIZED",
            "Ошибка конфигурации платёжной системы. Свяжитесь с поддержкой.",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    except BadRequestError as e:
        logger.error(f"YooKassa BadRequest for user {request.user.id}: {e}", exc_info=True)
        return _err(
            "INVALID_PAYMENT_REQUEST",
            "Некорректные данные платежа. Попробуйте позже или свяжитесь с поддержкой.",
            status.HTTP_400_BAD_REQUEST,
        )

    except ApiError as e:
        # Общая ошибка YooKassa API (включает все наследников, но ловим последней)
        logger.error(f"YooKassa API error for user {request.user.id}: {e}", exc_info=True)
        return _err(
            "YOOKASSA_API_ERROR",
            "Ошибка платёжной системы. Попробуйте позже.",
            status.HTTP_502_BAD_GATEWAY,
        )

    except Exception as e:
        # Неожиданная ошибка (не от YooKassa)
        logger.error(f"Unexpected error creating payment for user {request.user.id}: {e}", exc_info=True)
        return _err(
            "PAYMENT_CREATE_FAILED",
            "Не удалось создать платеж. Попробуйте позже.",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([PaymentCreationThrottle])  # [SECURITY] 20 req/hour
def bind_card_start(request):
    """
    POST /api/v1/billing/bind-card/start/
    Платёж на 1₽, чтобы сохранить карту для будущих рекуррентных платежей.

    Важно:
    - Это НЕ подписка. Это "технический" платёж, чтобы получить payment_method_id.
    - Дальше webhook должен сохранить payment_method_id в Subscription.
    """
    return_url = _validate_return_url(request.data.get("return_url"), request)

    try:
        subscription = _get_or_create_user_subscription(request.user)

        yk = YooKassaService()
        yk_payment = yk.create_payment(
            amount=Decimal("1.00"),
            description="Привязка карты для автопродления PRO",
            return_url=return_url,
            save_payment_method=True,
            metadata={"user_id": str(request.user.id), "purpose": "card_binding"},
        )

        payment = Payment.objects.create(
            user=request.user,
            subscription=subscription,
            amount=Decimal("1.00"),
            currency="RUB",
            status="PENDING",
            provider="YOOKASSA",
            description="Привязка карты для автопродления PRO",
            yookassa_payment_id=yk_payment["id"],
            save_payment_method=True,
            is_recurring=False,
        )

        SecurityAuditLogger.log_payment_created(
            user=request.user,
            amount=1.0,
            plan="card_binding",
            request=request,
        )

        return Response(
            {"confirmation_url": yk_payment["confirmation_url"], "payment_id": str(payment.id)},
            status=status.HTTP_201_CREATED,
        )

    except ForbiddenError as e:
        logger.error(
            f"YooKassa Forbidden (card binding) for user {request.user.id}: {e}. "
            "Card binding requires recurring to be enabled.",
            exc_info=True
        )
        return _err(
            "CARD_BINDING_NOT_AVAILABLE",
            "Привязка карты временно недоступна. Свяжитесь с поддержкой.",
            status.HTTP_403_FORBIDDEN,
        )

    except UnauthorizedError as e:
        logger.error(f"YooKassa Unauthorized (card binding) for user {request.user.id}: {e}", exc_info=True)
        return _err(
            "YOOKASSA_UNAUTHORIZED",
            "Ошибка конфигурации платёжной системы. Свяжитесь с поддержкой.",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    except ApiError as e:
        logger.error(f"YooKassa API error (card binding) for user {request.user.id}: {e}", exc_info=True)
        return _err(
            "YOOKASSA_API_ERROR",
            "Ошибка платёжной системы. Попробуйте позже.",
            status.HTTP_502_BAD_GATEWAY,
        )

    except Exception as e:
        logger.error(f"Unexpected error creating card binding payment for user {request.user.id}: {e}", exc_info=True)
        return _err(
            "BINDING_PAYMENT_CREATE_FAILED",
            "Не удалось создать платёж для привязки карты. Попробуйте позже.",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([PaymentCreationThrottle])  # [SECURITY] 20 req/hour (admin-only, но throttle всё равно)
def create_test_live_payment(request):
    """
    POST /api/v1/billing/create-test-live-payment/
    Тестовый платеж на 1₽ на боевом магазине (доступ только админам).

    Условия доступа:
    - пользователь привязан к Telegram (request.user.telegram_profile)
    - telegram_id в settings.TELEGRAM_ADMINS
    - settings.YOOKASSA_MODE == 'prod'
    """
    telegram_user = getattr(request.user, "telegram_profile", None)
    if not telegram_user:
        return _err("FORBIDDEN", "Доступ запрещён: пользователь не привязан к Telegram", status.HTTP_403_FORBIDDEN)

    telegram_admins = getattr(settings, "TELEGRAM_ADMINS", set())
    if telegram_user.telegram_id not in telegram_admins:
        return _err("FORBIDDEN", "Доступ запрещён: только для админов", status.HTTP_403_FORBIDDEN)

    if getattr(settings, "YOOKASSA_MODE", "") != "prod":
        return _err("FORBIDDEN", "Доступно только в prod режиме", status.HTTP_403_FORBIDDEN)

    return_url = _validate_return_url(request.data.get("return_url"), request)

    # План TEST_LIVE должен быть создан в админке (code=TEST_LIVE, is_test=True)
    try:
        test_plan = SubscriptionPlan.objects.get(code="TEST_LIVE", is_test=True, is_active=True)
    except SubscriptionPlan.DoesNotExist:
        return _err(
            "TEST_PLAN_NOT_FOUND",
            "Тестовый план TEST_LIVE не найден. Создайте plan: code=TEST_LIVE, is_test=True.",
            status.HTTP_404_NOT_FOUND,
        )

    try:
        subscription = _get_or_create_user_subscription(request.user)

        yk = YooKassaService()
        yk_payment = yk.create_payment(
            amount=test_plan.price,
            description=f"TEST_LIVE payment by admin {request.user.id}",
            return_url=return_url,
            save_payment_method=False,
            metadata={"user_id": str(request.user.id), "purpose": "test_live"},
        )

        payment = Payment.objects.create(
            user=request.user,
            subscription=subscription,
            plan=test_plan,
            amount=test_plan.price,
            currency="RUB",
            status="PENDING",
            provider="YOOKASSA",
            description="TEST_LIVE payment",
            yookassa_payment_id=yk_payment["id"],
            save_payment_method=False,
            is_recurring=False,
        )

        SecurityAuditLogger.log_payment_created(
            user=request.user,
            amount=float(payment.amount),
            plan="TEST_LIVE (admin test)",
            request=request,
        )

        return Response(
            {
                "payment_id": str(payment.id),
                "yookassa_payment_id": payment.yookassa_payment_id,
                "confirmation_url": yk_payment["confirmation_url"],
                "test_mode": True,
                "amount": str(payment.amount),
                "yookassa_mode": getattr(settings, "YOOKASSA_MODE", ""),
            },
            status=status.HTTP_201_CREATED,
        )

    except ForbiddenError as e:
        logger.error(f"YooKassa Forbidden (test payment) for admin {request.user.id}: {e}", exc_info=True)
        return _err(
            "YOOKASSA_FORBIDDEN",
            "Тестовый платёж заблокирован платёжной системой. Проверьте настройки YooKassa.",
            status.HTTP_403_FORBIDDEN,
        )

    except UnauthorizedError as e:
        logger.error(f"YooKassa Unauthorized (test payment) for admin {request.user.id}: {e}", exc_info=True)
        return _err(
            "YOOKASSA_UNAUTHORIZED",
            "Ошибка авторизации в YooKassa. Проверьте учётные данные.",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    except ApiError as e:
        logger.error(f"YooKassa API error (test payment) for admin {request.user.id}: {e}", exc_info=True)
        return _err(
            "YOOKASSA_API_ERROR",
            "Ошибка YooKassa API. Попробуйте позже.",
            status.HTTP_502_BAD_GATEWAY,
        )

    except Exception as e:
        logger.error(f"Unexpected error creating test payment for admin {request.user.id}: {e}", exc_info=True)
        return _err(
            "PAYMENT_CREATE_FAILED",
            "Не удалось создать тестовый платёж.",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
