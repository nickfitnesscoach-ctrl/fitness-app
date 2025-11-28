"""
Serializers for Telegram integration.
"""

from rest_framework import serializers
from .models import TelegramUser, PersonalPlanSurvey, PersonalPlan
from apps.users.serializers import ProfileSerializer
from apps.nutrition.serializers import DailyGoalSerializer


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
    is_admin = serializers.BooleanField(default=False)


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


class WebAppAuthUserSerializer(serializers.Serializer):
    """
    Информация о пользователе для WebApp аутентификации.
    Возвращает базовые данные пользователя из Telegram.
    """
    id = serializers.IntegerField()
    telegram_id = serializers.IntegerField()
    username = serializers.CharField(allow_null=True, allow_blank=True)
    first_name = serializers.CharField(allow_null=True, allow_blank=True)
    last_name = serializers.CharField(allow_null=True, allow_blank=True)


class WebAppAuthResponseSerializer(serializers.Serializer):
    """
    Полный ответ endpoint'а /webapp/auth/.
    Включает информацию о пользователе, профиле, целях и правах администратора.
    """
    user = WebAppAuthUserSerializer()
    profile = ProfileSerializer()
    goals = DailyGoalSerializer(allow_null=True)
    is_admin = serializers.BooleanField()


class PersonalPlanSurveySerializer(serializers.ModelSerializer):
    """Serializer для опроса Personal Plan."""

    class Meta:
        model = PersonalPlanSurvey
        fields = [
            'id',
            'user',
            'gender',
            'age',
            'height_cm',
            'weight_kg',
            'target_weight_kg',
            'activity',
            'training_level',
            'body_goals',
            'health_limitations',
            'body_now_id',
            'body_now_label',
            'body_now_file',
            'body_ideal_id',
            'body_ideal_label',
            'body_ideal_file',
            'timezone',
            'utc_offset_minutes',
            'completed_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CreatePersonalPlanSurveySerializer(serializers.Serializer):
    """
    Serializer для создания опроса Personal Plan от бота.
    Бот не передаёт user - он определяется по telegram_id.
    """

    telegram_id = serializers.IntegerField(required=True)
    gender = serializers.ChoiceField(choices=['male', 'female'], required=True)
    age = serializers.IntegerField(min_value=14, max_value=80, required=True)
    height_cm = serializers.IntegerField(min_value=120, max_value=250, required=True)
    weight_kg = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=30, max_value=300, required=True)
    target_weight_kg = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=30, max_value=300, required=False, allow_null=True)
    activity = serializers.ChoiceField(choices=['sedentary', 'light', 'moderate', 'active', 'very_active'], required=True)
    training_level = serializers.CharField(max_length=32, required=False, allow_blank=True, allow_null=True)
    body_goals = serializers.ListField(child=serializers.CharField(), required=False, allow_empty=True)
    health_limitations = serializers.ListField(child=serializers.CharField(), required=False, allow_empty=True)
    body_now_id = serializers.IntegerField(required=True)
    body_now_label = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    body_now_file = serializers.CharField(required=True)
    body_ideal_id = serializers.IntegerField(required=True)
    body_ideal_label = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    body_ideal_file = serializers.CharField(required=True)
    timezone = serializers.CharField(max_length=64, default='Europe/Moscow')
    utc_offset_minutes = serializers.IntegerField(required=True)


class PersonalPlanSerializer(serializers.ModelSerializer):
    """Serializer для Personal Plan."""

    class Meta:
        model = PersonalPlan
        fields = [
            'id',
            'user',
            'survey',
            'ai_text',
            'ai_model',
            'prompt_version',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class CreatePersonalPlanSerializer(serializers.Serializer):
    """
    Serializer для создания Personal Plan от бота.
    Бот не передаёт user - он определяется по telegram_id.
    """

    telegram_id = serializers.IntegerField(required=True)
    survey_id = serializers.IntegerField(required=False, allow_null=True)
    ai_text = serializers.CharField(required=True)
    ai_model = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    prompt_version = serializers.CharField(max_length=20, required=False, allow_blank=True, allow_null=True)
