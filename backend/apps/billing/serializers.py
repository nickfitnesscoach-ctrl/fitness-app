"""
billing/serializers.py

DRF serializers для billing.

Зачем этот файл:
- централизованная и строгая валидация входных данных (чтобы views были тонкими)
- единые форматы ответов для планов/платежей/подписки

Принципы:
- plan_code валидируем против БД (SubscriptionPlan)
- запрещаем создавать платежи для FREE (price <= 0)
- не доверяем сумме/дням с фронта — это НЕ поля запросов

Важно:
- в проекте есть legacy поле SubscriptionPlan.name, но SSOT = SubscriptionPlan.code
"""

from __future__ import annotations

from typing import Optional

from rest_framework import serializers

from .models import Payment, SubscriptionPlan

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _get_plan_by_code_or_legacy(plan_code: str) -> Optional[SubscriptionPlan]:
    """
    Ищем план по:
    - code (новое поле)
    - name (legacy fallback)
    Возвращаем None, если не найден.

    [SECURITY FIX 2024-12]: Исключаем is_test=True планы.
    Test-планы доступны ТОЛЬКО через admin endpoint (create_test_live_payment).
    """
    try:
        # ВАЖНО: is_test=False блокирует TEST_LIVE и другие тестовые планы
        return SubscriptionPlan.objects.get(code=plan_code, is_active=True, is_test=False)
    except SubscriptionPlan.DoesNotExist:
        try:
            return SubscriptionPlan.objects.get(name=plan_code, is_active=True, is_test=False)
        except SubscriptionPlan.DoesNotExist:
            return None


# ---------------------------------------------------------------------
# Public Plans
# ---------------------------------------------------------------------

# ---------------------------------------------------------------------
# Public Plans
# ---------------------------------------------------------------------

# [DEPRECATED] Marketing copy (features, display_name override, is_popular) moved to frontend.
# See frontend/src/features/billing/config/planCopy.ts for SSOT.
# old_price is now a DB field (SubscriptionPlan.old_price), editable via Django Admin.


class SubscriptionPlanPublicSerializer(serializers.ModelSerializer):
    """
    Публичный сериализатор тарифов для /billing/plans/

    Billing truth (from DB, editable via Django Admin):
    - code, price, old_price, duration_days, limits

    Marketing copy (deprecated, moved to frontend PLAN_COPY):
    - features → always []
    - is_popular → always False
    - display_name → DB value (frontend overrides with copy.displayName)
    """

    # [DEPRECATED] Remove after 2026-02-15
    # These fields return neutral values; frontend uses PLAN_COPY instead.
    features = serializers.SerializerMethodField()
    is_popular = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = SubscriptionPlan
        fields = [
            "code",
            "display_name",
            "price",
            "old_price",
            "is_popular",
            "duration_days",
            "features",
            # Legacy fields (kept for backward compat if needed, but UI uses features[])
            "daily_photo_limit",
            "history_days",
            "ai_recognition",
            "advanced_stats",
            "priority_support",
        ]

    def get_features(self, obj: SubscriptionPlan) -> list[str]:
        # [DEPRECATED] Remove after 2026-02-15
        # Features moved to frontend SSOT (PLAN_COPY in planCopy.ts).
        return []

    def get_is_popular(self, obj: SubscriptionPlan) -> bool:
        # [DEPRECATED] Remove after 2026-02-15
        # is_popular moved to frontend SSOT (PLAN_COPY in planCopy.ts).
        return False

    def get_display_name(self, obj: SubscriptionPlan) -> str:
        # [DEPRECATED] Remove after 2026-02-15
        # display_name override moved to frontend (PLAN_COPY.displayName).
        return obj.display_name


# ---------------------------------------------------------------------
# Legacy subscribe serializer (старый endpoint /billing/subscribe)
# ---------------------------------------------------------------------


class SubscribeSerializer(serializers.Serializer):
    """
    Legacy serializer для POST /billing/subscribe
    Там historically поле называется "plan" (а не plan_code).
    """

    plan = serializers.CharField(max_length=50)

    def validate_plan(self, value: str) -> str:
        plan = _get_plan_by_code_or_legacy(value)
        if not plan:
            raise serializers.ValidationError("Тарифный план не найден или выключен.")
        if plan.price <= 0:
            raise serializers.ValidationError("Нельзя создать платеж для бесплатного тарифа.")
        return value


# ---------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------


class CreatePaymentRequestSerializer(serializers.Serializer):
    """
    Новый запрос для POST /billing/create-payment/

    Body:
      {
        "plan_code": "PRO_MONTHLY" | "PRO_YEARLY" | legacy: "MONTHLY" | "YEARLY",
        "return_url": "https://..." (опционально)
      }
    """

    plan_code = serializers.CharField(max_length=50)
    return_url = serializers.URLField(required=False, allow_null=True)

    def validate_plan_code(self, value: str) -> str:
        plan = _get_plan_by_code_or_legacy(value)
        if not plan:
            raise serializers.ValidationError("Тарифный план не найден или выключен.")
        if plan.price <= 0:
            raise serializers.ValidationError("Нельзя создать платеж для бесплатного тарифа.")
        return value


class PaymentSerializer(serializers.ModelSerializer):
    """
    Сериализация Payment для legacy /billing/payments (пагинация).
    """

    plan_code = serializers.SerializerMethodField()
    plan_name = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            "id",
            "amount",
            "currency",
            "status",
            "created_at",
            "paid_at",
            "description",
            "provider",
            "yookassa_payment_id",
            "plan_code",
            "plan_name",
        ]

    def get_plan_code(self, obj: Payment) -> Optional[str]:
        return obj.plan.code if obj.plan else None

    def get_plan_name(self, obj: Payment) -> Optional[str]:
        return obj.plan.display_name if obj.plan else None


# ---------------------------------------------------------------------
# Auto-renew
# ---------------------------------------------------------------------


class AutoRenewToggleSerializer(serializers.Serializer):
    """
    POST /billing/subscription/autorenew/
    Body: { "enabled": true|false }
    """

    enabled = serializers.BooleanField()


# ---------------------------------------------------------------------
# Backward-compatible serializers placeholders
# (Если где-то в проекте остались импорты старых классов,
#  мы сохраняем их имена как алиасы/простые классы.)
# ---------------------------------------------------------------------

# Эти классы фигурировали в старом views.py как импорты.
# Сейчас они не обязательны, но оставляем для обратной совместимости,
# чтобы не словить ImportError в других местах проекта.


class SubscriptionPlanSerializer(SubscriptionPlanPublicSerializer):
    """Back-compat alias: раньше использовали этот класс."""

    pass


class SubscriptionSerializer(serializers.Serializer):
    """
    Минимальный сериализатор подписки для legacy /billing/plan endpoint.
    (Полноценная карточка подписки отдаётся через views.get_subscription_details)
    """

    plan_code = serializers.CharField()
    plan_name = serializers.CharField()
    expires_at = serializers.CharField(allow_null=True)
    auto_renew = serializers.BooleanField()


class PaymentMethodSerializer(serializers.Serializer):
    """
    Совместимость: простая структура для payment method.
    """

    is_attached = serializers.BooleanField()
    card_mask = serializers.CharField(allow_null=True)
    card_brand = serializers.CharField(allow_null=True)


class CurrentPlanResponseSerializer(serializers.Serializer):
    """Back-compat placeholder."""

    status = serializers.CharField()
    data = serializers.DictField()


class SubscriptionStatusSerializer(serializers.Serializer):
    """Back-compat placeholder for /billing/me/ response."""

    plan_code = serializers.CharField()
    plan_name = serializers.CharField()
    expires_at = serializers.CharField(allow_null=True)
    is_active = serializers.BooleanField()
    daily_photo_limit = serializers.IntegerField(allow_null=True)
    used_today = serializers.IntegerField()
    remaining_today = serializers.IntegerField(allow_null=True)
    test_live_payment_available = serializers.BooleanField(required=False)


class AutoRenewToggleSerializerLegacy(AutoRenewToggleSerializer):
    """Back-compat alias if старый импорт где-то остался."""

    pass


class PaymentHistoryItemSerializer(serializers.Serializer):
    """Back-compat placeholder (в новом API это формируется в views)."""

    id = serializers.CharField()
    amount = serializers.FloatField()
    currency = serializers.CharField()
    status = serializers.CharField()
    paid_at = serializers.CharField(allow_null=True)
    description = serializers.CharField()
