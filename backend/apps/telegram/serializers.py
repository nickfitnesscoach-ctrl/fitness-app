"""
Serializers for Telegram integration.
"""

from rest_framework import serializers
from .models import TelegramUser


class TelegramUserSerializer(serializers.ModelSerializer):
    """Serializer для Telegram пользователя."""

    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = TelegramUser
        fields = [
            'telegram_id',
            'username',
            'first_name',
            'last_name',
            'display_name',
            'language_code',
            'is_premium',
            'ai_test_completed',
            'ai_test_answers',
            'recommended_calories',
            'recommended_protein',
            'recommended_fat',
            'recommended_carbs',
            'created_at',
        ]
        read_only_fields = ['created_at']


class TelegramAuthSerializer(serializers.Serializer):
    """Serializer для ответа аутентификации."""

    access = serializers.CharField()
    refresh = serializers.CharField()
    user = TelegramUserSerializer()


class SaveTestResultsSerializer(serializers.Serializer):
    """
    Serializer для сохранения результатов AI теста от бота.
    """

    telegram_id = serializers.IntegerField(required=True)
    first_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    username = serializers.CharField(max_length=255, required=False, allow_blank=True)

    # Ответы пользователя из теста
    answers = serializers.JSONField(required=False)

    def validate_telegram_id(self, value):
        """Проверка telegram_id."""
        if value <= 0:
            raise serializers.ValidationError("Telegram ID должен быть положительным числом")
        return value

    def validate_answers(self, value):
        """Валидация структуры ответов."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Answers должны быть словарем")
        return value
