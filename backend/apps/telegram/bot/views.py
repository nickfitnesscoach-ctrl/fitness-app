"""
Bot API views for Telegram integration.
"""

import logging
from datetime import datetime, date

from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.telegram.models import TelegramUser, PersonalPlanSurvey, PersonalPlan
from apps.telegram.serializers import (
    CreatePersonalPlanSurveySerializer,
    PersonalPlanSurveySerializer,
    CreatePersonalPlanSerializer,
    PersonalPlanSerializer,
    SaveTestResultsSerializer,
)
from apps.nutrition.models import DailyGoal

logger = logging.getLogger(__name__)


@extend_schema(tags=['Telegram'])
@api_view(['POST'])
@permission_classes([AllowAny])
def save_test_results(request):
    """
    Endpoint для сохранения результатов опроса из Telegram бота.

    POST /api/v1/telegram/save-test/
    """
    serializer = SaveTestResultsSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        data = serializer.validated_data
        telegram_id = data['telegram_id']
        first_name = data.get('first_name', '')
        last_name = data.get('last_name', '')
        username = data.get('username', '')
        answers = data.get('answers', {})

        goal_mapping = {
            'fat_loss': 'weight_loss',
            'muscle_gain': 'weight_gain',
            'maintenance': 'maintenance',
            'weight_loss': 'weight_loss',
            'weight_gain': 'weight_gain'
        }

        with transaction.atomic():
            try:
                telegram_user = TelegramUser.objects.get(telegram_id=telegram_id)
                created = False
                user = telegram_user.user
            except TelegramUser.DoesNotExist:
                user = User.objects.create_user(
                    username=f"tg_{telegram_id}",
                    first_name=first_name,
                    last_name=last_name,
                    email=f"tg{telegram_id}@telegram.user"
                )

                telegram_user = TelegramUser.objects.create(
                    telegram_id=telegram_id,
                    user=user,
                    first_name=first_name,
                    last_name=last_name,
                    username=username,
                )
                created = True

            profile = user.profile

            profile.telegram_id = telegram_id
            profile.telegram_username = username

            gender_value = answers.get('gender', 'M')
            profile.gender = gender_value[0].upper() if gender_value else 'M'

            profile.weight = answers.get('weight')
            profile.height = answers.get('height')

            activity_mapping = {
                'minimal': 'sedentary',
                'low': 'lightly_active',
                'medium': 'moderately_active',
                'high': 'very_active'
            }
            activity_value = answers.get('activity_level', 'medium')
            profile.activity_level = activity_mapping.get(activity_value, 'sedentary')

            goal_value = answers.get('goal', 'maintenance')
            profile.goal_type = goal_mapping.get(goal_value, 'maintenance')

            target_weight = answers.get('target_weight')
            if target_weight:
                profile.target_weight = target_weight

            timezone_value = answers.get('timezone')
            if timezone_value:
                profile.timezone = timezone_value

            training_level = answers.get('training_level')
            if training_level:
                profile.training_level = training_level

            goals = answers.get('goals', [])
            if goals:
                profile.goals = goals

            health_restrictions = answers.get('health_restrictions', [])
            if health_restrictions:
                profile.health_restrictions = health_restrictions

            current_body_type = answers.get('current_body_type')
            if current_body_type:
                profile.current_body_type = current_body_type

            ideal_body_type = answers.get('ideal_body_type')
            if ideal_body_type:
                profile.ideal_body_type = ideal_body_type

            age = answers.get('age')
            if age:
                current_year = date.today().year
                birth_year = current_year - age
                profile.birth_date = date(birth_year, 1, 1)

            profile.save()

            telegram_user.ai_test_completed = True
            telegram_user.ai_test_answers = answers
            telegram_user.save()

            try:
                DailyGoal.objects.filter(user=user, is_active=True).update(is_active=False)

                goals = DailyGoal.calculate_goals(user)

                DailyGoal.objects.create(
                    user=user,
                    calories=goals['calories'],
                    protein=goals['protein'],
                    fat=goals['fat'],
                    carbohydrates=goals['carbohydrates'],
                    source='AUTO',
                    is_active=True
                )

                telegram_user.recommended_calories = goals['calories']
                telegram_user.recommended_protein = goals['protein']
                telegram_user.recommended_fat = goals['fat']
                telegram_user.recommended_carbs = goals['carbohydrates']
                telegram_user.save()

            except Exception:
                pass

        return Response({
            "status": "success",
            "user_id": user.id,
            "message": "Данные теста сохранены в FoodMind AI",
            "created": created
        })

    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Telegram'],
    summary="Get invite link",
    description="Получить ссылку-приглашение на Telegram бота"
)
@api_view(['GET'])
@permission_classes([AllowAny])
def get_invite_link(request):
    """
    GET: Получить ссылку-приглашение

    GET /api/v1/telegram/invite-link/
    """
    bot_username = settings.TELEGRAM_BOT_USERNAME
    invite_link = f"https://t.me/{bot_username}?start=invite"

    return Response({
        "link": invite_link
    }, status=status.HTTP_200_OK)


@extend_schema(
    tags=['Telegram - Personal Plan'],
    summary="Get or create user by telegram_id",
    description="Получить или создать пользователя по Telegram ID (для бота)"
)
@api_view(['GET'])
@permission_classes([AllowAny])
def get_user_or_create(request):
    """
    Получить или создать пользователя по telegram_id.

    GET /api/v1/telegram/users/get-or-create/?telegram_id=123456789&username=johndoe&full_name=John%20Doe
    """
    telegram_id = request.query_params.get('telegram_id')
    username = request.query_params.get('username', '')
    full_name = request.query_params.get('full_name', '')

    if not telegram_id:
        return Response(
            {"error": "telegram_id is required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        telegram_id = int(telegram_id)
    except ValueError:
        return Response(
            {"error": "Invalid telegram_id"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        telegram_user = TelegramUser.objects.select_related('user').get(telegram_id=telegram_id)
        created = False

        if username and telegram_user.username != username:
            telegram_user.username = username
            telegram_user.save(update_fields=['username'])

    except TelegramUser.DoesNotExist:
        user = User.objects.create_user(
            username=f"tg_{telegram_id}",
            email=f"tg_{telegram_id}@telegram.user",
            first_name=full_name,
        )

        name_parts = full_name.split(' ', 1)
        first_name = name_parts[0] if name_parts else ''
        last_name = name_parts[1] if len(name_parts) > 1 else ''

        telegram_user = TelegramUser.objects.create(
            user=user,
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
        )
        created = True

    return Response({
        "id": telegram_user.id,
        "user_id": telegram_user.user.id,
        "telegram_id": telegram_user.telegram_id,
        "username": telegram_user.username,
        "first_name": telegram_user.first_name,
        "last_name": telegram_user.last_name,
        "created": created,
    })


@extend_schema(
    tags=['Telegram - Personal Plan'],
    summary="Create Personal Plan Survey",
    description="Создать ответ на опрос Personal Plan от бота"
)
@api_view(['POST'])
@permission_classes([AllowAny])
def create_survey(request):
    """
    Создать ответ на опрос Personal Plan от бота.

    POST /api/v1/telegram/personal-plan/survey/
    """
    serializer = CreatePersonalPlanSurveySerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    telegram_id = data.pop('telegram_id')

    with transaction.atomic():
        try:
            telegram_user = TelegramUser.objects.get(telegram_id=telegram_id)
            user = telegram_user.user
        except TelegramUser.DoesNotExist:
            user = User.objects.create_user(
                username=f"tg_{telegram_id}",
                email=f"tg_{telegram_id}@telegram.user",
            )
            telegram_user = TelegramUser.objects.create(
                user=user,
                telegram_id=telegram_id,
            )

        survey = PersonalPlanSurvey.objects.create(
            user=user,
            completed_at=datetime.now(),
            **data
        )

    result_serializer = PersonalPlanSurveySerializer(survey)
    return Response(result_serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=['Telegram - Personal Plan'],
    summary="Create Personal Plan",
    description="Создать AI-генерированный Personal Plan от бота"
)
@api_view(['POST'])
@permission_classes([AllowAny])
def create_plan(request):
    """
    Создать Personal Plan от бота.

    POST /api/v1/telegram/personal-plan/plan/
    """
    serializer = CreatePersonalPlanSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    telegram_id = data.pop('telegram_id')
    survey_id = data.pop('survey_id', None)

    try:
        telegram_user = TelegramUser.objects.get(telegram_id=telegram_id)
        user = telegram_user.user
    except TelegramUser.DoesNotExist:
        return Response(
            {"error": "User not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    survey = None
    if survey_id:
        try:
            survey = PersonalPlanSurvey.objects.get(id=survey_id, user=user)
        except PersonalPlanSurvey.DoesNotExist:
            return Response(
                {"error": "Survey not found"},
                status=status.HTTP_404_NOT_FOUND
            )

    today_start = datetime.combine(date.today(), datetime.min.time())
    plans_today = PersonalPlan.objects.filter(
        user=user,
        created_at__gte=today_start
    ).count()

    max_plans_per_day = 3
    if plans_today >= max_plans_per_day:
        return Response(
            {"error": f"Daily limit of {max_plans_per_day} plans reached"},
            status=status.HTTP_429_TOO_MANY_REQUESTS
        )

    plan = PersonalPlan.objects.create(
        user=user,
        survey=survey,
        **data
    )

    result_serializer = PersonalPlanSerializer(plan)
    return Response(result_serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=['Telegram - Personal Plan'],
    summary="Count plans created today",
    description="Подсчитать количество планов пользователя за сегодня"
)
@api_view(['GET'])
@permission_classes([AllowAny])
def count_plans_today(request):
    """
    Подсчитать количество планов пользователя за сегодня.

    GET /api/v1/telegram/personal-plan/count-today/?telegram_id=123456789
    """
    telegram_id = request.query_params.get('telegram_id')

    if not telegram_id:
        return Response(
            {"error": "telegram_id is required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        telegram_id = int(telegram_id)
    except ValueError:
        return Response(
            {"error": "Invalid telegram_id"},
            status=status.HTTP_400_BAD_REQUEST
        )

    max_plans = getattr(settings, 'PERSONAL_PLAN_DAILY_LIMIT', 3)

    try:
        telegram_user = TelegramUser.objects.get(telegram_id=telegram_id)
    except TelegramUser.DoesNotExist:
        return Response({
            "count": 0,
            "limit": max_plans,
            "can_create": True,
        })

    today_start = datetime.combine(date.today(), datetime.min.time())
    count = PersonalPlan.objects.filter(
        user=telegram_user.user,
        created_at__gte=today_start
    ).count()

    return Response({
        "count": count,
        "limit": max_plans,
        "can_create": count < max_plans,
    })
