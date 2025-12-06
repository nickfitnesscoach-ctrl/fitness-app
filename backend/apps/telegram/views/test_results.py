"""
Test results views for Telegram integration.
"""

import logging
from datetime import date

from django.contrib.auth.models import User
from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.telegram.models import TelegramUser
from apps.telegram.serializers import SaveTestResultsSerializer
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
