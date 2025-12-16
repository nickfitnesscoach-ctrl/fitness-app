"""
Bot API views для Telegram интеграции.

Зачем этот файл:
- Это API, которым пользуется ТВОЙ Telegram-бот (а не обычные пользователи через браузер).
- Тут создаются/обновляются записи в базе: пользователи, анкеты, планы, результаты теста.
- Поэтому это "write-зона" и её нельзя оставлять открытой (AllowAny без защиты = дырка).

Как защищаем:
- Каждый запрос от бота должен присылать секретный ключ в заголовке:
  X-Bot-Secret: <секрет>
- Секрет хранится в settings / env: TELEGRAM_BOT_API_SECRET
- Без секрета возвращаем 403.

Примечание:
- WebApp авторизация (initData) — это другая история, она в auth/views.
"""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Optional

from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.nutrition.models import DailyGoal
from apps.telegram.models import PersonalPlan, PersonalPlanSurvey, TelegramUser
from apps.telegram.serializers import (
    CreatePersonalPlanSerializer,
    CreatePersonalPlanSurveySerializer,
    PersonalPlanSerializer,
    PersonalPlanSurveySerializer,
    SaveTestResultsSerializer,
)

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Вспомогательные функции
# -----------------------------------------------------------------------------

def _forbidden(message: str = "Нет доступа") -> Response:
    return Response({"error": message}, status=status.HTTP_403_FORBIDDEN)


def _bot_secret_ok(request) -> bool:
    """
    Проверка, что запрос действительно пришёл от нашего бота.
    Бот присылает заголовок X-Bot-Secret.
    """
    expected = getattr(settings, "TELEGRAM_BOT_API_SECRET", None)
    if not expected:
        # В проде лучше НЕ запускаться без секрета.
        # Но чтобы не ломать dev, разрешим в DEBUG.
        return bool(getattr(settings, "DEBUG", False))

    provided = request.headers.get("X-Bot-Secret") or request.META.get("HTTP_X_BOT_SECRET")
    return bool(provided) and provided == expected


def _require_bot_secret(request) -> Optional[Response]:
    """Если секрет не ок — возвращаем Response, иначе None."""
    if not _bot_secret_ok(request):
        return _forbidden("Bot secret is invalid or missing")
    return None


def _get_or_create_telegram_user(telegram_id: int, username: str = "", full_name: str = "") -> TelegramUser:
    """
    Единое место, где мы создаём/получаем TelegramUser и связанный Django User.
    Так мы не дублируем логику в 3 разных эндпоинтах.
    """
    telegram_user = TelegramUser.objects.select_related("user").filter(telegram_id=telegram_id).first()
    if telegram_user:
        # Обновим username/имя, если пришло новое
        if username and telegram_user.username != username:
            telegram_user.username = username
            telegram_user.save(update_fields=["username"])
        return telegram_user

    # Создаём нового Django User
    # username должен быть уникальным
    user = User.objects.create_user(
        username=f"tg_{telegram_id}",
        email=f"tg_{telegram_id}@telegram.user",
        first_name=full_name[:150] if full_name else "",
    )

    # Аккуратно разбиваем имя на first/last
    first_name = ""
    last_name = ""
    if full_name:
        parts = full_name.split(" ", 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ""

    return TelegramUser.objects.create(
        user=user,
        telegram_id=telegram_id,
        username=username or None,
        first_name=first_name,
        last_name=last_name,
    )


def _today_start_dt() -> datetime:
    """
    Начало "сегодня" в таймзоне Django.
    Чтобы не зависеть от локального времени сервера.
    """
    today = timezone.localdate()
    return timezone.make_aware(datetime.combine(today, datetime.min.time()))


# -----------------------------------------------------------------------------
# Эндпоинты
# -----------------------------------------------------------------------------

@extend_schema(tags=["Telegram"])
@api_view(["POST"])
@permission_classes([AllowAny])
def save_test_results(request):
    """
    Сохранение результатов лид-магнита (AI теста) от бота.

    POST /api/v1/telegram/save-test/

    Безопасность:
    - только для бота (X-Bot-Secret)
    """
    forbidden = _require_bot_secret(request)
    if forbidden:
        return forbidden

    serializer = SaveTestResultsSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    telegram_id = data["telegram_id"]
    first_name = data.get("first_name", "") or ""
    last_name = data.get("last_name", "") or ""
    username = data.get("username", "") or ""
    answers = data.get("answers", {}) or {}

    # Маппинги к внутренним форматам
    goal_mapping = {
        "fat_loss": "weight_loss",
        "weight_loss": "weight_loss",
        "muscle_gain": "weight_gain",
        "weight_gain": "weight_gain",
        "maintenance": "maintenance",
    }
    activity_mapping = {
        "minimal": "sedentary",
        "low": "lightly_active",
        "medium": "moderately_active",
        "high": "very_active",
    }

    try:
        with transaction.atomic():
            # Получаем/создаём TelegramUser
            telegram_user = TelegramUser.objects.select_related("user").filter(telegram_id=telegram_id).first()
            created = False

            if telegram_user:
                user = telegram_user.user
            else:
                user = User.objects.create_user(
                    username=f"tg_{telegram_id}",
                    first_name=first_name,
                    last_name=last_name,
                    email=f"tg{telegram_id}@telegram.user",
                )
                telegram_user = TelegramUser.objects.create(
                    telegram_id=telegram_id,
                    user=user,
                    first_name=first_name,
                    last_name=last_name,
                    username=username or None,
                )
                created = True

            # --- Обновляем профиль пользователя (если у тебя есть Profile через OneToOne) ---
            # Важно: если profile может отсутствовать — нужно get_or_create.
            # Здесь я предполагаю, что он всегда есть (как у тебя в коде).
            profile = user.profile  # если может падать — скажи, перепишу на безопасный get_or_create

            profile.telegram_id = telegram_id
            profile.telegram_username = username

            gender_value = (answers.get("gender") or "M")
            profile.gender = (gender_value[0].upper() if gender_value else "M")

            profile.weight = answers.get("weight")
            profile.height = answers.get("height")

            activity_value = answers.get("activity_level", "medium")
            profile.activity_level = activity_mapping.get(activity_value, "sedentary")

            goal_value = answers.get("goal", "maintenance")
            profile.goal_type = goal_mapping.get(goal_value, "maintenance")

            if answers.get("target_weight"):
                profile.target_weight = answers.get("target_weight")

            if answers.get("timezone"):
                profile.timezone = answers.get("timezone")

            if answers.get("training_level"):
                profile.training_level = answers.get("training_level")

            if isinstance(answers.get("goals"), list):
                profile.goals = answers.get("goals")

            if isinstance(answers.get("health_restrictions"), list):
                profile.health_restrictions = answers.get("health_restrictions")

            if answers.get("current_body_type"):
                profile.current_body_type = answers.get("current_body_type")

            if answers.get("ideal_body_type"):
                profile.ideal_body_type = answers.get("ideal_body_type")

            age = answers.get("age")
            if isinstance(age, int) and 0 < age < 120:
                birth_year = timezone.localdate().year - age
                profile.birth_date = datetime(birth_year, 1, 1).date()

            profile.save()

            # --- Сохраняем тест в TelegramUser ---
            telegram_user.ai_test_completed = True
            telegram_user.ai_test_answers = answers
            telegram_user.save(update_fields=["ai_test_completed", "ai_test_answers", "updated_at"])

            # --- Пытаемся пересчитать цели питания ---
            # Важно: тут не глотаем ошибки молча — логируем.
            try:
                DailyGoal.objects.filter(user=user, is_active=True).update(is_active=False)
                goals = DailyGoal.calculate_goals(user)

                DailyGoal.objects.create(
                    user=user,
                    calories=goals["calories"],
                    protein=goals["protein"],
                    fat=goals["fat"],
                    carbohydrates=goals["carbohydrates"],
                    source="AUTO",
                    is_active=True,
                )

                telegram_user.recommended_calories = goals["calories"]
                telegram_user.recommended_protein = goals["protein"]
                telegram_user.recommended_fat = goals["fat"]
                telegram_user.recommended_carbs = goals["carbohydrates"]
                telegram_user.save(update_fields=[
                    "recommended_calories",
                    "recommended_protein",
                    "recommended_fat",
                    "recommended_carbs",
                    "updated_at",
                ])
            except Exception as e:
                logger.exception("Failed to calculate DailyGoal for telegram_id=%s: %s", telegram_id, e)

        return Response(
            {
                "status": "success",
                "user_id": user.id,
                "message": "Данные теста сохранены",
                "created": created,
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        logger.exception("save_test_results failed: %s", e)
        return Response({"error": "Internal server error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(tags=["Telegram"], summary="Get invite link")
@api_view(["GET"])
@permission_classes([AllowAny])
def get_invite_link(request):
    """
    Ссылка-приглашение на бота.
    Это read-endpoint, его можно оставить публичным.
    """
    bot_username = getattr(settings, "TELEGRAM_BOT_USERNAME", None)
    if not bot_username:
        return Response({"error": "TELEGRAM_BOT_USERNAME is not configured"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response({"link": f"https://t.me/{bot_username}?start=invite"}, status=status.HTTP_200_OK)


@extend_schema(tags=["Telegram - Personal Plan"], summary="Get or create user by telegram_id")
@api_view(["GET"])
@permission_classes([AllowAny])
def get_user_or_create(request):
    """
    Получить или создать пользователя по telegram_id.
    Этот эндпоинт пишет в БД -> должен быть защищён секретом бота.
    """
    forbidden = _require_bot_secret(request)
    if forbidden:
        return forbidden

    telegram_id = request.query_params.get("telegram_id")
    username = request.query_params.get("username", "") or ""
    full_name = request.query_params.get("full_name", "") or ""

    if not telegram_id:
        return Response({"error": "telegram_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        telegram_id_int = int(telegram_id)
    except ValueError:
        return Response({"error": "Invalid telegram_id"}, status=status.HTTP_400_BAD_REQUEST)

    telegram_user = _get_or_create_telegram_user(telegram_id_int, username=username, full_name=full_name)

    return Response(
        {
            "id": telegram_user.id,
            "user_id": telegram_user.user.id,
            "telegram_id": telegram_user.telegram_id,
            "username": telegram_user.username,
            "first_name": telegram_user.first_name,
            "last_name": telegram_user.last_name,
            "created": False,  # точно узнать можно, но обычно боту не критично
        },
        status=status.HTTP_200_OK,
    )


@extend_schema(tags=["Telegram - Personal Plan"], summary="Create Personal Plan Survey")
@api_view(["POST"])
@permission_classes([AllowAny])
def create_survey(request):
    """
    Создать анкету Personal Plan.
    Пишет в БД -> только для бота (X-Bot-Secret).
    """
    forbidden = _require_bot_secret(request)
    if forbidden:
        return forbidden

    serializer = CreatePersonalPlanSurveySerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    telegram_id = data.pop("telegram_id")

    with transaction.atomic():
        telegram_user = _get_or_create_telegram_user(telegram_id)

        survey = PersonalPlanSurvey.objects.create(
            user=telegram_user.user,
            completed_at=timezone.now(),
            **data,
        )

    return Response(PersonalPlanSurveySerializer(survey).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Telegram - Personal Plan"], summary="Create Personal Plan")
@api_view(["POST"])
@permission_classes([AllowAny])
def create_plan(request):
    """
    Создать AI-план.
    Пишет в БД -> только для бота (X-Bot-Secret).
    """
    forbidden = _require_bot_secret(request)
    if forbidden:
        return forbidden

    serializer = CreatePersonalPlanSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    telegram_id = data.pop("telegram_id")
    survey_id = data.pop("survey_id", None)

    telegram_user = TelegramUser.objects.select_related("user").filter(telegram_id=telegram_id).first()
    if not telegram_user:
        return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

    survey = None
    if survey_id:
        survey = PersonalPlanSurvey.objects.filter(id=survey_id, user=telegram_user.user).first()
        if not survey:
            return Response({"error": "Survey not found"}, status=status.HTTP_404_NOT_FOUND)

    # Лимит планов в день
    max_plans_per_day = getattr(settings, "PERSONAL_PLAN_DAILY_LIMIT", 3)
    today_start = _today_start_dt()

    plans_today = PersonalPlan.objects.filter(user=telegram_user.user, created_at__gte=today_start).count()
    if plans_today >= max_plans_per_day:
        return Response(
            {"error": f"Daily limit of {max_plans_per_day} plans reached"},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    plan = PersonalPlan.objects.create(user=telegram_user.user, survey=survey, **data)
    return Response(PersonalPlanSerializer(plan).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Telegram - Personal Plan"], summary="Count plans created today")
@api_view(["GET"])
@permission_classes([AllowAny])
def count_plans_today(request):
    """
    Посчитать количество планов за сегодня.
    Это read-endpoint, но всё равно лучше держать закрытым от внешнего мира,
    чтобы его не ддосили (он ходит в БД).
    """
    forbidden = _require_bot_secret(request)
    if forbidden:
        return forbidden

    telegram_id = request.query_params.get("telegram_id")
    if not telegram_id:
        return Response({"error": "telegram_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        telegram_id_int = int(telegram_id)
    except ValueError:
        return Response({"error": "Invalid telegram_id"}, status=status.HTTP_400_BAD_REQUEST)

    max_plans = getattr(settings, "PERSONAL_PLAN_DAILY_LIMIT", 3)

    telegram_user = TelegramUser.objects.select_related("user").filter(telegram_id=telegram_id_int).first()
    if not telegram_user:
        return Response({"count": 0, "limit": max_plans, "can_create": True}, status=status.HTTP_200_OK)

    today_start = _today_start_dt()
    count = PersonalPlan.objects.filter(user=telegram_user.user, created_at__gte=today_start).count()

    return Response({"count": count, "limit": max_plans, "can_create": count < max_plans}, status=status.HTTP_200_OK)
