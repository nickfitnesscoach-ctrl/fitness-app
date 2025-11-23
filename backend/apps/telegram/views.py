"""
Views for Telegram integration.
"""

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
    get_user_id_from_init_data,
    telegram_admin_required,
    validate_init_data,
)
from .models import TelegramUser
from .serializers import (
    TelegramAuthSerializer,
    TelegramUserSerializer,
    SaveTestResultsSerializer,
)
from apps.nutrition.models import DailyGoal
from apps.users.models import Profile


@telegram_admin_required
def trainer_admin_panel(request):
    """Simple admin panel endpoint protected by Telegram WebApp validation."""

    return JsonResponse({"ok": True, "section": "trainer_panel", "user_id": request.telegram_user_id})


@extend_schema(tags=["TrainerPanel"])
@api_view(["POST"])
@permission_classes([AllowAny])
def trainer_panel_auth(request):
    """Validate Telegram WebApp initData and ensure the user is an admin."""

    raw_init_data = (
        request.data.get("init_data")
        or request.data.get("initData")
        or request.headers.get("X-Telegram-Init-Data")
        or request.headers.get("X_TG_INIT_DATA")
    )

    if not raw_init_data:
        return Response({"detail": "Нет доступа"}, status=status.HTTP_403_FORBIDDEN)

    parsed_data = validate_init_data(raw_init_data, settings.TELEGRAM_BOT_TOKEN)
    if not parsed_data:
        return Response({"detail": "Нет доступа"}, status=status.HTTP_403_FORBIDDEN)

    user_id = get_user_id_from_init_data(parsed_data)
    admins = getattr(settings, "TELEGRAM_ADMINS", set()) or set()
    if isinstance(admins, set):
        admin_ids = admins
    else:
        admin_ids = {int(admin) for admin in admins}

    if user_id is None or user_id not in admin_ids:
        return Response({"detail": "Нет доступа"}, status=status.HTTP_403_FORBIDDEN)

    return Response(
        {
            "ok": True,
            "user_id": user_id,
            "role": "admin",
        }
    )


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
