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
