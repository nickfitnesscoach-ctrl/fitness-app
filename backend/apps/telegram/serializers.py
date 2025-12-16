"""
Serializers для Telegram интеграции (DRF).

Зачем этот файл:
- Serializers = "переводчики" между JSON <-> Python/Django моделями.
- Они решают две задачи:
  1) Валидация входных данных (что прислал бот/миниапп)
  2) Формирование ответа (что отдаём наружу)

Важно для прода:
- Нельзя "случайно" отдать лишние поля (PII / внутренние id).
- Нельзя принимать мусор/невалидные данные, иначе в БД будет бардак.
"""
from __future__ import annotations

from rest_framework import serializers

from apps.nutrition.serializers import DailyGoalSerializer
from apps.users.serializers import ProfileSerializer

from .models import PersonalPlan, PersonalPlanSurvey, TelegramUser

# ============================================================================
# 1) Утилиты валидации (маленькие функции, чтобы не повторяться)
# ============================================================================

def _validate_positive_int(value: int, field_name: str) -> int:
    """Общая проверка, что число > 0."""
    if value is None or int(value) <= 0:
        raise serializers.ValidationError(f"{field_name} должен быть положительным числом")
    return int(value)


# ============================================================================
# 2) Telegram User (то, что мы храним/показываем о пользователе Telegram)
# ============================================================================

class TelegramUserSerializer(serializers.ModelSerializer):
    """
    Что отдаём фронту/миниапп по TelegramUser.

    Важно:
    - Мы отдаём только то, что действительно нужно клиенту.
    - created_at — read_only, его нельзя прислать и "подделать".
    """

    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = TelegramUser
        fields = [
            "telegram_id",
            "username",
            "first_name",
            "last_name",
            "display_name",
            "language_code",
            "is_premium",
            "ai_test_completed",
            "ai_test_answers",
            "recommended_calories",
            "recommended_protein",
            "recommended_fat",
            "recommended_carbs",
            "created_at",
        ]
        read_only_fields = ["created_at"]


class TelegramAuthSerializer(serializers.Serializer):
    """
    Ответ после аутентификации Telegram пользователя.

    Обычно это:
    - access/refresh токены (если используется JWT)
    - user: данные TelegramUser
    - is_admin: флаг админки (панель тренера и т.п.)
    """
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = TelegramUserSerializer()
    is_admin = serializers.BooleanField(default=False)


# ============================================================================
# 3) AI тест (результаты теста от Telegram-бота)
# ============================================================================

class SaveTestResultsSerializer(serializers.Serializer):
    """
    Входные данные: бот присылает результаты AI-теста.

    Что валидируем:
    - telegram_id обязателен и > 0
    - answers должны быть dict (словарь)
    """
    telegram_id = serializers.IntegerField(required=True)
    first_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    username = serializers.CharField(max_length=255, required=False, allow_blank=True)

    answers = serializers.JSONField(required=False)

    def validate_telegram_id(self, value: int) -> int:
        return _validate_positive_int(value, "telegram_id")

    def validate_answers(self, value):
        if value is None:
            return value
        if not isinstance(value, dict):
            raise serializers.ValidationError("answers должны быть объектом (словарём)")
        return value


# ============================================================================
# 4) WebApp Auth (Mini App авторизация: отдаём user+profile+goals+is_admin)
# ============================================================================

class WebAppAuthUserSerializer(serializers.Serializer):
    """
    Минимальный набор данных о пользователе для Mini App.
    Это НЕ модельный сериализатор, потому что тут часто склеиваются данные
    из Telegram + нашей базы.
    """
    id = serializers.IntegerField()
    telegram_id = serializers.IntegerField()
    username = serializers.CharField(allow_null=True, allow_blank=True)
    first_name = serializers.CharField(allow_null=True, allow_blank=True)
    last_name = serializers.CharField(allow_null=True, allow_blank=True)


class WebAppAuthResponseSerializer(serializers.Serializer):
    """
    Ответ эндпоинта /webapp/auth/

    Возвращаем:
    - user: базовая инфа (telegram)
    - profile: профиль пользователя в нашем приложении
    - goals: дневные цели (может быть null если целей нет)
    - is_admin: признак доступа к админским вещам
    """
    user = WebAppAuthUserSerializer()
    profile = ProfileSerializer()
    goals = DailyGoalSerializer(allow_null=True)
    is_admin = serializers.BooleanField()


# ============================================================================
# 5) Personal Plan Survey (анкета перед генерацией плана)
# ============================================================================

class PersonalPlanSurveySerializer(serializers.ModelSerializer):
    """
    Выходной сериализатор анкеты (например, для админки/панели).

    Важно:
    - user оставляем в выдаче, потому что это внутренняя штука (скорее всего).
      Если это уходит наружу пользователю — лучше заменить на read_only user_id
      или убрать вовсе (зависит от твоей логики).
    """
    class Meta:
        model = PersonalPlanSurvey
        fields = [
            "id",
            "user",
            "gender",
            "age",
            "height_cm",
            "weight_kg",
            "target_weight_kg",
            "activity",
            "training_level",
            "body_goals",
            "health_limitations",
            "body_now_id",
            "body_now_label",
            "body_now_file",
            "body_ideal_id",
            "body_ideal_label",
            "body_ideal_file",
            "timezone",
            "utc_offset_minutes",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class CreatePersonalPlanSurveySerializer(serializers.Serializer):
    """
    Входной сериализатор: бот создаёт анкету.

    Ключевая идея:
    - бот НЕ передаёт user
    - user определяется на сервере по telegram_id

    Этот сериализатор только проверяет JSON.
    Сохранение в БД делается во view/service.
    """
    telegram_id = serializers.IntegerField(required=True)

    gender = serializers.ChoiceField(choices=["male", "female"], required=True)
    age = serializers.IntegerField(min_value=14, max_value=80, required=True)
    height_cm = serializers.IntegerField(min_value=120, max_value=250, required=True)

    weight_kg = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=30, max_value=300, required=True
    )
    target_weight_kg = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=30, max_value=300, required=False, allow_null=True
    )

    activity = serializers.ChoiceField(
        choices=["sedentary", "light", "moderate", "active", "very_active"], required=True
    )

    training_level = serializers.CharField(max_length=32, required=False, allow_blank=True, allow_null=True)

    body_goals = serializers.ListField(child=serializers.CharField(), required=False, allow_empty=True)
    health_limitations = serializers.ListField(child=serializers.CharField(), required=False, allow_empty=True)

    body_now_id = serializers.IntegerField(required=True)
    body_now_label = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    body_now_file = serializers.CharField(required=True)

    body_ideal_id = serializers.IntegerField(required=True)
    body_ideal_label = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    body_ideal_file = serializers.CharField(required=True)

    timezone = serializers.CharField(max_length=64, default="Europe/Moscow")
    utc_offset_minutes = serializers.IntegerField(required=True)

    def validate_telegram_id(self, value: int) -> int:
        return _validate_positive_int(value, "telegram_id")

    def validate_body_now_id(self, value: int) -> int:
        return _validate_positive_int(value, "body_now_id")

    def validate_body_ideal_id(self, value: int) -> int:
        return _validate_positive_int(value, "body_ideal_id")


# ============================================================================
# 6) Personal Plan (AI план)
# ============================================================================

class PersonalPlanSerializer(serializers.ModelSerializer):
    """
    Выходной сериализатор плана.

    Как и с survey:
    - user/survey можно отдавать, если это внутренняя ручка.
    - если это отдаётся клиенту напрямую — лучше контролировать поля строго.
    """
    class Meta:
        model = PersonalPlan
        fields = [
            "id",
            "user",
            "survey",
            "ai_text",
            "ai_model",
            "prompt_version",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class CreatePersonalPlanSerializer(serializers.Serializer):
    """
    Входной сериализатор: бот отправляет готовый AI план, который мы сохраняем.

    Важно:
    - user определяется по telegram_id
    - survey_id опционален (иногда план без привязки к анкете)
    """
    telegram_id = serializers.IntegerField(required=True)
    survey_id = serializers.IntegerField(required=False, allow_null=True)

    ai_text = serializers.CharField(required=True)
    ai_model = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    prompt_version = serializers.CharField(max_length=20, required=False, allow_blank=True, allow_null=True)

    def validate_telegram_id(self, value: int) -> int:
        return _validate_positive_int(value, "telegram_id")

    def validate_survey_id(self, value):
        if value is None:
            return value
        return _validate_positive_int(value, "survey_id")
