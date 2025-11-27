"""
Сериализаторы для billing endpoints.
"""

from rest_framework import serializers
from .models import SubscriptionPlan, Subscription, Payment, Refund


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """Сериализатор для тарифного плана."""

    features = serializers.SerializerMethodField()

    class Meta:
        model = SubscriptionPlan
        fields = [
            'name',
            'display_name',
            'description',
            'price',
            'duration_days',
            'features',
            'is_active',
        ]

    def get_features(self, obj):
        """Возвращает словарь с features."""
        return obj.get_features_dict()


class SubscriptionSerializer(serializers.ModelSerializer):
    """Сериализатор для подписки пользователя."""

    plan = SubscriptionPlanSerializer(read_only=True)
    days_remaining = serializers.IntegerField(read_only=True)

    class Meta:
        model = Subscription
        fields = [
            'id',
            'plan',
            'start_date',
            'end_date',
            'is_active',
            'auto_renew',
            'days_remaining',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PaymentSerializer(serializers.ModelSerializer):
    """Сериализатор для платежа."""

    plan_name = serializers.CharField(source='plan.display_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id',
            'plan_name',
            'amount',
            'currency',
            'status',
            'status_display',
            'provider',
            'is_recurring',
            'description',
            'created_at',
            'paid_at',
        ]
        read_only_fields = ['id', 'created_at', 'paid_at']


class SubscribeSerializer(serializers.Serializer):
    """Сериализатор для оформления подписки."""

    plan = serializers.ChoiceField(
        choices=['MONTHLY', 'YEARLY'],
        help_text='Тип тарифного плана'
    )

    def validate_plan(self, value):
        """Проверяет, что план существует и активен."""
        try:
            plan = SubscriptionPlan.objects.get(name=value, is_active=True)
        except SubscriptionPlan.DoesNotExist:
            raise serializers.ValidationError(f'Тарифный план "{value}" не найден или неактивен.')

        return value


class RefundSerializer(serializers.ModelSerializer):
    """Сериализатор для возврата."""

    payment_id = serializers.UUIDField(source='payment.id', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Refund
        fields = [
            'id',
            'payment_id',
            'amount',
            'status',
            'status_display',
            'reason',
            'created_at',
            'completed_at',
        ]
        read_only_fields = ['id', 'created_at', 'completed_at']


class CurrentPlanResponseSerializer(serializers.Serializer):
    """Сериализатор для ответа на GET /billing/plan"""

    subscription = SubscriptionSerializer()
    available_plans = SubscriptionPlanSerializer(many=True)


class PaymentMethodSerializer(serializers.Serializer):
    """Сериализатор для информации о способе оплаты."""

    is_attached = serializers.BooleanField(
        help_text='Привязана ли карта для автопродления'
    )
    card_mask = serializers.CharField(
        allow_null=True,
        help_text='Маска карты, например "•••• 1234"'
    )
    card_brand = serializers.CharField(
        allow_null=True,
        help_text='Тип карты: Visa, MasterCard, МИР и т.д.'
    )


class SubscriptionStatusSerializer(serializers.Serializer):
    """Сериализатор для полного статуса подписки (GET /billing/subscription/)."""

    plan = serializers.CharField(
        help_text='Код плана: "free" или "pro"'
    )
    plan_display = serializers.CharField(
        help_text='Отображаемое название плана'
    )
    expires_at = serializers.DateField(
        allow_null=True,
        help_text='Дата окончания подписки (null для free)'
    )
    is_active = serializers.BooleanField(
        help_text='Активна ли подписка'
    )
    autorenew_available = serializers.BooleanField(
        help_text='Доступно ли автопродление (есть ли привязанная карта)'
    )
    autorenew_enabled = serializers.BooleanField(
        help_text='Включено ли автопродление'
    )
    payment_method = PaymentMethodSerializer(
        help_text='Информация о привязанном способе оплаты'
    )


class AutoRenewToggleSerializer(serializers.Serializer):
    """Сериализатор для включения/отключения автопродления."""

    enabled = serializers.BooleanField(
        required=True,
        help_text='Включить (true) или выключить (false) автопродление'
    )


class PaymentHistoryItemSerializer(serializers.Serializer):
    """Сериализатор для элемента истории платежей."""

    id = serializers.UUIDField(
        help_text='ID платежа'
    )
    amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='Сумма платежа'
    )
    currency = serializers.CharField(
        help_text='Валюта платежа'
    )
    status = serializers.CharField(
        help_text='Статус платежа в нижнем регистре'
    )
    paid_at = serializers.DateTimeField(
        allow_null=True,
        help_text='Дата и время оплаты (ISO 8601)'
    )
    description = serializers.CharField(
        help_text='Описание платежа'
    )


class PaymentHistoryResponseSerializer(serializers.Serializer):
    """Сериализатор для ответа на GET /billing/payments/."""

    results = PaymentHistoryItemSerializer(many=True)
