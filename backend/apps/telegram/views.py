"""
Views for Telegram integration.
"""

import json
import logging
import os

from django.conf import settings
from django.contrib.auth.models import User
from django.http import JsonResponse
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .authentication import TelegramWebAppAuthentication
from .telegram_auth import (
    TelegramAdminPermission,
    telegram_admin_required,
)
from .services.webapp_auth import get_webapp_auth_service
from .models import TelegramUser, PersonalPlanSurvey, PersonalPlan
from .serializers import (
    TelegramAuthSerializer,
    TelegramUserSerializer,
    SaveTestResultsSerializer,
    WebAppAuthResponseSerializer,
    CreatePersonalPlanSurveySerializer,
    PersonalPlanSurveySerializer,
    CreatePersonalPlanSerializer,
    PersonalPlanSerializer,
)
from apps.nutrition.models import DailyGoal
from apps.users.models import Profile
from datetime import datetime, date


logger = logging.getLogger(__name__)


@telegram_admin_required
def trainer_admin_panel(request):
    """Simple admin panel endpoint protected by Telegram WebApp validation."""

    return JsonResponse({"ok": True, "section": "trainer_panel", "user_id": request.telegram_user_id})


@extend_schema(tags=["TrainerPanel"])
@api_view(["POST"])
@permission_classes([AllowAny])
def trainer_panel_auth(request):
    """Validate Telegram WebApp initData and ensure the user is an admin."""

    logger.info("[TrainerPanel] Auth request started")

    # 1. Получаем initData
    raw_init_data = (
        request.data.get("init_data")
        or request.data.get("initData")
        or request.headers.get("X-Telegram-Init-Data")
    )

    if not raw_init_data:
        logger.warning("[TrainerPanel] No initData in request")
        return Response({"detail": "Нет доступа"}, status=status.HTTP_403_FORBIDDEN)

    logger.info("[TrainerPanel] initData length: %d", len(raw_init_data))

    # 2. Валидация через ЕДИНЫЙ сервис
    auth_service = get_webapp_auth_service()
    parsed_data = auth_service.validate_init_data(raw_init_data)

    if not parsed_data:
        logger.warning("[TrainerPanel] initData validation failed")
        return Response({"detail": "Нет доступа"}, status=status.HTTP_403_FORBIDDEN)

    logger.info("[TrainerPanel] initData validation successful")

    # 3. Получаем user_id
    user_id = auth_service.get_user_id_from_init_data(parsed_data)
    if not user_id:
        logger.error("[TrainerPanel] Failed to extract user_id")
        return Response({"detail": "Нет доступа"}, status=status.HTTP_403_FORBIDDEN)

    logger.info("[TrainerPanel] Extracted user_id: %s", user_id)

    # 4. Проверка прав админа (ЕДИНЫЙ источник правды!)
    admins = settings.TELEGRAM_ADMINS  # Set[int] из settings

    if not admins:
        logger.warning("[TrainerPanel] Admin list empty, allowing access (DEV mode?)")
        return Response({
            "ok": True,
            "user_id": user_id,
            "role": "admin",
            "warning": "admin_list_empty"
        })

    if user_id not in admins:
        logger.warning(
            "[TrainerPanel] Access denied for user_id=%s (admins: %s)",
            user_id, admins
        )
        return Response({"detail": "Нет доступа"}, status=status.HTTP_403_FORBIDDEN)

    logger.info("[TrainerPanel] Access granted for user_id=%s", user_id)
    return Response({
        "ok": True,
        "user_id": user_id,
        "role": "admin"
    })


@extend_schema(tags=['Telegram'])
@api_view(['POST'])
@permission_classes([AllowAny])
def telegram_auth(request):
    """
    Аутентификация через Telegram Mini App.

    POST /api/v1/telegram/auth/

    Headers:
        X-Telegram-Init-Data: <initData from Telegram.WebApp.initData>

    Response:
        {
            "access": "jwt_access_token",
            "refresh": "jwt_refresh_token",
            "user": {
                "id": 1,
                "username": "tg_123456789",
                "telegram_id": 123456789,
                "first_name": "John",
                "completed_ai_test": false
            }
        }
    """
    authenticator = TelegramWebAppAuthentication()

    try:
        user, _ = authenticator.authenticate(request)

        if not user:
            return Response(
                {"error": "Authentication failed"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Генерируем JWT токены
        refresh = RefreshToken.for_user(user)

        # Получаем Telegram профиль
        telegram_user = user.telegram_profile

        serializer = TelegramAuthSerializer({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': telegram_user
        })

        return Response(serializer.data)

    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@extend_schema(tags=['Telegram'])
@api_view(['POST'])
@permission_classes([AllowAny])
def webapp_auth(request):
    """
    Единый endpoint для авторизации Telegram WebApp (Этап 2 roadmap).

    POST /api/v1/telegram/webapp/auth/

    Headers:
        X-Telegram-Init-Data: <initData from Telegram.WebApp.initData>

    Body (альтернативно):
        {
            "init_data": "<initData from Telegram.WebApp.initData>"
        }

    Response:
        {
            "user": {
                "id": 123,
                "telegram_id": 987654321,
                "username": "user123",
                "first_name": "John",
                "last_name": "Doe"
            },
            "profile": {
                "gender": "M",
                "birth_date": "1990-01-01",
                "height": 180,
                "weight": 80,
                "goal_type": "weight_loss",
                "activity_level": "sedentary",
                "timezone": "Europe/Moscow",
                "age": 34,
                "is_complete": true
            },
            "goals": {
                "id": 1,
                "calories": 2000,
                "protein": 150,
                "fat": 55,
                "carbohydrates": 225,
                "source": "AUTO",
                "is_active": true
            },
            "is_admin": false
        }
    """
    # Используем существующую аутентификацию через TelegramWebAppAuthentication
    authenticator = TelegramWebAppAuthentication()

    try:
        result = authenticator.authenticate(request)

        if not result:
            logger.warning("[WebAppAuth] Authentication failed: no result from authenticator")
            return Response(
                {"error": "Authentication failed"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        user, auth_data = result

        if not user:
            logger.warning("[WebAppAuth] Authentication failed: no user")
            return Response(
                {"error": "Authentication failed"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        logger.info(f"[WebAppAuth] User authenticated: {user.id} (username: {user.username})")

        # Получаем или создаём TelegramUser
        try:
            telegram_user = user.telegram_profile
        except TelegramUser.DoesNotExist:
            logger.warning(f"[WebAppAuth] User {user.id} without TelegramUser, attempting to create")
            # Пытаемся извлечь данные из request (если доступны)
            telegram_id = getattr(request, 'telegram_id', None)
            if not telegram_id and hasattr(user, 'profile') and user.profile.telegram_id:
                telegram_id = user.profile.telegram_id

            if telegram_id:
                telegram_user = TelegramUser.objects.create(
                    user=user,
                    telegram_id=telegram_id,
                    username=user.username.replace('tg_', '') if user.username.startswith('tg_') else '',
                    first_name=user.first_name,
                    last_name=user.last_name,
                )
                logger.info(f"[WebAppAuth] Created TelegramUser {telegram_id} for user {user.id}")
            else:
                logger.error(f"[WebAppAuth] Cannot create TelegramUser for user {user.id}: no telegram_id")
                return Response(
                    {"error": "Telegram profile creation failed"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        # Получаем или создаём Profile
        profile, created = Profile.objects.get_or_create(user=user)
        if created:
            logger.info(f"[WebAppAuth] Created empty Profile for user {user.id}")

        # Получаем активную цель КБЖУ
        active_goal = (
            DailyGoal.objects
            .filter(user=user, is_active=True)
            .order_by('-created_at')
            .first()
        )

        # Определяем, является ли пользователь администратором
        admin_ids = set()

        # Читаем список админов из настроек
        telegram_admins = getattr(settings, 'TELEGRAM_ADMINS', '')
        if telegram_admins:
            try:
                # TELEGRAM_ADMINS может быть строкой "123,456" или set
                if isinstance(telegram_admins, str):
                    admin_ids.update(
                        int(x.strip())
                        for x in telegram_admins.split(',')
                        if x.strip().isdigit()
                    )
                elif isinstance(telegram_admins, (set, list)):
                    admin_ids.update(int(x) for x in telegram_admins)
            except (ValueError, AttributeError) as e:
                logger.warning(f"[WebAppAuth] Failed to parse TELEGRAM_ADMINS: {e}")

        bot_admin_id = getattr(settings, 'BOT_ADMIN_ID', None)
        if bot_admin_id:
            try:
                admin_ids.add(int(bot_admin_id))
            except (ValueError, TypeError) as e:
                logger.warning(f"[WebAppAuth] Failed to parse BOT_ADMIN_ID: {e}")

        is_admin = telegram_user.telegram_id in admin_ids
        logger.info(f"[WebAppAuth] User {user.id} admin status: {is_admin} (telegram_id: {telegram_user.telegram_id}, admins: {admin_ids})")

        # Формируем ответ
        response_data = {
            'user': {
                'id': user.id,
                'telegram_id': telegram_user.telegram_id,
                'username': telegram_user.username or '',
                'first_name': telegram_user.first_name or '',
                'last_name': telegram_user.last_name or '',
            },
            'profile': profile,
            'goals': active_goal,
            'is_admin': is_admin,
        }

        serializer = WebAppAuthResponseSerializer(response_data)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        logger.exception(f"[WebAppAuth] Unexpected error: {e}")
        return Response(
            {"error": "Internal server error"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(tags=['Telegram'])
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def telegram_profile(request):
    """
    Получить Telegram профиль текущего пользователя.

    GET /api/v1/telegram/profile/

    Authorization: Bearer <jwt_token>

    Response:
        {
            "telegram_id": 123456789,
            "username": "johndoe",
            "first_name": "John",
            "last_name": "Doe",
            "language_code": "ru",
            "is_premium": false,
            "ai_test_completed": true,
            "recommended_calories": 2100,
            "recommended_protein": 130.00,
            "recommended_fat": 70.00,
            "recommended_carbs": 240.00
        }
    """
    try:
        telegram_user = request.user.telegram_profile
        serializer = TelegramUserSerializer(telegram_user)
        return Response(serializer.data)

    except TelegramUser.DoesNotExist:
        return Response(
            {"error": "Telegram profile not found"},
            status=status.HTTP_404_NOT_FOUND
        )


@extend_schema(tags=['Telegram'])
@api_view(['POST'])
@permission_classes([AllowAny])
def save_test_results(request):
    """
    Endpoint для сохранения результатов опроса из Telegram бота.

    POST /api/v1/telegram/save-test/

    Body:
    {
        "telegram_id": 123456789,
        "first_name": "Иван",
        "last_name": "Иванов",
        "username": "ivan123",
        "answers": {
            "gender": "male",
            "age": 30,
            "height": 180,
            "weight": 80,
            "target_weight": 75,
            "activity_level": "medium",
            "training_level": "intermediate",
            "goals": ["weight_loss"],
            "health_restrictions": ["none"],
            "current_body_type": 2,
            "ideal_body_type": 3,
            "timezone": "Europe/Moscow"
        }
    }

    Response:
        {
            "status": "success",
            "user_id": 1,
            "message": "Данные теста сохранены в FoodMind AI",
            "created": true
        }
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

        # Маппинг значений бота на Django модель
        # Бот использует: fat_loss, maintenance, muscle_gain
        # Django ожидает: weight_loss, maintenance, weight_gain
        goal_mapping = {
            'fat_loss': 'weight_loss',
            'muscle_gain': 'weight_gain',
            'maintenance': 'maintenance',
            'weight_loss': 'weight_loss',  # На случай если бот отправит правильное значение
            'weight_gain': 'weight_gain'
        }

        # Получаем или создаем TelegramUser
        try:
            telegram_user = TelegramUser.objects.get(telegram_id=telegram_id)
            created = False
            user = telegram_user.user
        except TelegramUser.DoesNotExist:
            # Создаем Django User
            user = User.objects.create_user(
                username=f"tg_{telegram_id}",
                first_name=first_name,
                last_name=last_name,
                email=f"tg{telegram_id}@telegram.user"
            )

            # Создаем TelegramUser со связью на User
            telegram_user = TelegramUser.objects.create(
                telegram_id=telegram_id,
                user=user,
                first_name=first_name,
                last_name=last_name,
                username=username,
            )
            created = True

        # Заполняем Profile данными из теста (для новых и существующих пользователей)
        profile = user.profile

        # Telegram данные
        profile.telegram_id = telegram_id
        profile.telegram_username = username

        # Gender должен быть 1 символ: 'M' или 'F'
        gender_value = answers.get('gender', 'M')
        profile.gender = gender_value[0].upper() if gender_value else 'M'

        # Базовые параметры
        profile.weight = answers.get('weight')
        profile.height = answers.get('height')

        # Маппинг activity_level
        activity_mapping = {
            'minimal': 'sedentary',
            'low': 'lightly_active',
            'medium': 'moderately_active',
            'high': 'very_active'
        }
        activity_value = answers.get('activity_level', 'medium')
        profile.activity_level = activity_mapping.get(activity_value, 'sedentary')

        # Маппинг goal значений
        goal_value = answers.get('goal', 'maintenance')
        profile.goal_type = goal_mapping.get(goal_value, 'maintenance')

        # Целевой вес (если указан)
        target_weight = answers.get('target_weight')
        if target_weight:
            profile.target_weight = target_weight

        # Часовой пояс (если указан)
        timezone_value = answers.get('timezone')
        if timezone_value:
            profile.timezone = timezone_value

        # Уровень тренированности
        training_level = answers.get('training_level')
        if training_level:
            profile.training_level = training_level

        # Цели (массив)
        goals = answers.get('goals', [])
        if goals:
            profile.goals = goals

        # Ограничения по здоровью (массив)
        health_restrictions = answers.get('health_restrictions', [])
        if health_restrictions:
            profile.health_restrictions = health_restrictions

        # Типы фигуры
        current_body_type = answers.get('current_body_type')
        if current_body_type:
            profile.current_body_type = current_body_type

        ideal_body_type = answers.get('ideal_body_type')
        if ideal_body_type:
            profile.ideal_body_type = ideal_body_type

        # Считаем возраст → birth_date
        age = answers.get('age')
        if age:
            from datetime import date
            current_year = date.today().year
            birth_year = current_year - age
            profile.birth_date = date(birth_year, 1, 1)

        profile.save()

        # Сохраняем результаты теста
        telegram_user.ai_test_completed = True
        telegram_user.ai_test_answers = answers
        telegram_user.save()

        # Создаем DailyGoal с автоматическим расчетом КБЖУ
        try:
            # Деактивируем старые цели
            DailyGoal.objects.filter(user=user, is_active=True).update(is_active=False)

            # Рассчитываем КБЖУ на основе данных профиля
            goals = DailyGoal.calculate_goals(user)

            # Создаем новую активную цель с автоматическим расчетом
            DailyGoal.objects.create(
                user=user,
                calories=goals['calories'],
                protein=goals['protein'],
                fat=goals['fat'],
                carbohydrates=goals['carbohydrates'],
                source='AUTO',
                is_active=True
            )

            # Сохраняем рассчитанные КБЖУ в TelegramUser для быстрого доступа
            telegram_user.recommended_calories = goals['calories']
            telegram_user.recommended_protein = goals['protein']
            telegram_user.recommended_fat = goals['fat']
            telegram_user.recommended_carbs = goals['carbohydrates']
            telegram_user.save()

        except Exception:
            # Если не удалось рассчитать (недостаточно данных), просто пропускаем
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
    summary="Get all clients/applications",
    description="Получить список всех клиентов, прошедших опрос через бота"
)
@api_view(['GET'])
@permission_classes([TelegramAdminPermission])
def get_applications_api(request):
    """
    API endpoint для получения списка клиентов.

    GET /api/v1/telegram/applications/

    Response:
        [
            {
                "id": 1,
                "telegram_id": 123456789,
                "first_name": "Иван",
                "last_name": "Петров",
                "username": "ivan_petrov",
                "display_name": "Иван Петров",
                "ai_test_completed": true,
                "recommended_calories": 1896,
                "recommended_protein": 142.2,
                "recommended_fat": 52.67,
                "recommended_carbs": 213.3,
                "created_at": "2024-01-15T10:30:00Z"
            }
        ]
    """
    # Получаем всех пользователей, которые завершили тест
    clients = TelegramUser.objects.filter(ai_test_completed=True).order_by('-created_at')

    # Формируем данные для ответа
    data = []
    for client in clients:
        data.append({
            "id": client.id,
            "telegram_id": str(client.telegram_id),
            "first_name": client.first_name or "",
            "last_name": client.last_name or "",
            "username": client.username or "",
            "display_name": client.display_name,
            "ai_test_completed": client.ai_test_completed,
            "recommended_calories": client.recommended_calories,
            "recommended_protein": client.recommended_protein,
            "recommended_fat": client.recommended_fat,
            "recommended_carbs": client.recommended_carbs,
            "created_at": client.created_at.isoformat(),
        })

    return Response(data, status=status.HTTP_200_OK)


@extend_schema(
    tags=['Telegram'],
    summary="Get list of clients",
    description="Получить список всех клиентов (applications с флагом is_client=True)"
)
@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def clients_list(request):
    """
    GET: Получить список клиентов
    POST: Добавить заявку в клиенты
    
    GET /api/v1/telegram/clients/
    POST /api/v1/telegram/clients/
    
    POST Body:
        {
            "id": 1,  # ID из TelegramUser
            "first_name": "Иван",
            ... (любые данные из Application)
        }
    """
    if request.method == 'GET':
        # Получаем всех клиентов (is_client=True)
        clients = TelegramUser.objects.filter(
            ai_test_completed=True,
            is_client=True
        ).order_by('-created_at')
        
        data = []
        for client in clients:
            data.append({
                "id": client.id,
                "telegram_id": str(client.telegram_id),
                "first_name": client.first_name or "",
                "last_name": client.last_name or "",
                "username": client.username or "",
                "display_name": client.display_name,
                "ai_test_completed": client.ai_test_completed,
                "recommended_calories": client.recommended_calories,
                "recommended_protein": client.recommended_protein,
                "recommended_fat": client.recommended_fat,
                "recommended_carbs": client.recommended_carbs,
                "created_at": client.created_at.isoformat(),
            })
        
        return Response(data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        # Добавить в клиенты
        client_id = request.data.get('id')
        
        if not client_id:
            return Response(
                {"error": "ID is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            telegram_user = TelegramUser.objects.get(id=client_id)
            telegram_user.is_client = True
            telegram_user.save()
            
            return Response({
                "status": "success",
                "message": "Client added successfully",
                "id": telegram_user.id
            }, status=status.HTTP_200_OK)
            
        except TelegramUser.DoesNotExist:
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND
            )


@extend_schema(
    tags=['Telegram'],
    summary="Delete client",
    description="Удалить клиента (убрать флаг is_client)"
)
@api_view(['DELETE'])
@permission_classes([AllowAny])
def client_detail(request, client_id):
    """
    DELETE: Удалить клиента
    
    DELETE /api/v1/telegram/clients/{id}/
    """
    try:
        telegram_user = TelegramUser.objects.get(id=client_id)
        telegram_user.is_client = False
        telegram_user.save()
        
        return Response({
            "status": "success",
            "message": "Client removed successfully"
        }, status=status.HTTP_200_OK)
        
    except TelegramUser.DoesNotExist:
        return Response(
            {"error": "Client not found"},
            status=status.HTTP_404_NOT_FOUND
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
    
    Response:
        {
            "link": "https://t.me/YourBot?start=invite_code"
        }
    """
    from django.conf import settings
    
    # Получаем имя бота из токена или используем дефолтное
    bot_token = settings.TELEGRAM_BOT_TOKEN
    
    # Извлекаем username бота (если есть) или используем дефолтное
    # В продакшене это должно быть настроено через переменные окружения
    bot_username = "Fit_Coach_bot"  # TODO: Получать из настроек или API Telegram
    
    # Генерируем уникальную ссылку (можно добавить referral code)
    invite_link = f"https://t.me/{bot_username}?start=invite"

    return Response({
        "link": invite_link
    }, status=status.HTTP_200_OK)


# ============================================================
# Personal Plan API (для бота)
# ============================================================


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

    Response:
        {
            "id": 1,
            "user_id": 5,
            "telegram_id": 123456789,
            "username": "johndoe",
            "first_name": "John",
            "last_name": "Doe",
            "created": false
        }
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

    # Получаем или создаём
    try:
        telegram_user = TelegramUser.objects.get(telegram_id=telegram_id)
        created = False

        # Обновляем username/full_name если изменились
        if username and telegram_user.username != username:
            telegram_user.username = username
            telegram_user.save()

    except TelegramUser.DoesNotExist:
        # Создаём
        user = User.objects.create_user(
            username=f"tg_{telegram_id}",
            first_name=full_name,
        )

        # Разбиваем full_name на first_name и last_name
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

    Body:
        {
            "telegram_id": 123456789,
            "gender": "male",
            "age": 30,
            "height_cm": 180,
            "weight_kg": 80.5,
            "target_weight_kg": 75.0,
            "activity": "moderate",
            "training_level": "intermediate",
            "body_goals": ["weight_loss", "muscle_gain"],
            "health_limitations": ["back_problems"],
            "body_now_id": 2,
            "body_now_label": "Атлетичное тело",
            "body_now_file": "body_2.png",
            "body_ideal_id": 3,
            "body_ideal_label": "Подтянутое тело",
            "body_ideal_file": "body_3.png",
            "timezone": "Europe/Moscow",
            "utc_offset_minutes": 180
        }
    """
    serializer = CreatePersonalPlanSurveySerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    telegram_id = data.pop('telegram_id')

    # Получаем или создаём пользователя
    try:
        telegram_user = TelegramUser.objects.get(telegram_id=telegram_id)
        user = telegram_user.user
    except TelegramUser.DoesNotExist:
        # Создаём нового пользователя
        user = User.objects.create_user(
            username=f"tg_{telegram_id}",
        )
        telegram_user = TelegramUser.objects.create(
            user=user,
            telegram_id=telegram_id,
        )

    # Создаём опрос
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

    Body:
        {
            "telegram_id": 123456789,
            "survey_id": 5,
            "ai_text": "Ваш персональный план питания и тренировок...",
            "ai_model": "meta-llama/llama-3.1-70b-instruct",
            "prompt_version": "v1.0"
        }
    """
    serializer = CreatePersonalPlanSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    telegram_id = data.pop('telegram_id')
    survey_id = data.pop('survey_id', None)

    # Получаем пользователя
    try:
        telegram_user = TelegramUser.objects.get(telegram_id=telegram_id)
        user = telegram_user.user
    except TelegramUser.DoesNotExist:
        return Response(
            {"error": "User not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    # Проверяем survey (если указан)
    survey = None
    if survey_id:
        try:
            survey = PersonalPlanSurvey.objects.get(id=survey_id, user=user)
        except PersonalPlanSurvey.DoesNotExist:
            return Response(
                {"error": "Survey not found"},
                status=status.HTTP_404_NOT_FOUND
            )

    # Проверяем лимит планов в день
    today_start = datetime.combine(date.today(), datetime.min.time())
    plans_today = PersonalPlan.objects.filter(
        user=user,
        created_at__gte=today_start
    ).count()

    max_plans_per_day = 3  # Или из settings
    if plans_today >= max_plans_per_day:
        return Response(
            {"error": f"Daily limit of {max_plans_per_day} plans reached"},
            status=status.HTTP_429_TOO_MANY_REQUESTS
        )

    # Создаём план
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

    Response:
        {
            "count": 2,
            "limit": 3,
            "can_create": true
        }
    """
    telegram_id = request.query_params.get('telegram_id')

    if not telegram_id:
        return Response(
            {"error": "telegram_id is required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        telegram_id = int(telegram_id)
        telegram_user = TelegramUser.objects.get(telegram_id=telegram_id)
    except (ValueError, TelegramUser.DoesNotExist):
        return Response(
            {"error": "User not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    today_start = datetime.combine(date.today(), datetime.min.time())
    count = PersonalPlan.objects.filter(
        user=telegram_user.user,
        created_at__gte=today_start
    ).count()

    max_plans = 3  # Или из settings

    return Response({
        "count": count,
        "limit": max_plans,
        "can_create": count < max_plans,
    })
