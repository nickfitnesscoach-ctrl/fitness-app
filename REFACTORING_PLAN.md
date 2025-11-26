# План архитектурного рефакторинга проекта Fitness-app

## Цель
Привести проект к архитектуре:
- ОДНА БД Postgres (единая схема для всего проекта)
- ЕДИНЫЙ источник бизнес-логики — backend (Django)
- Бот НЕ работает с БД напрямую, а только через REST API backend

---

## ШАГ 1: АУДИТ БД И ДОСТУПА К ДАННЫМ ✅

### Текущая конфигурация БД:

**Backend (Django):**
- Главная БД: **PostgreSQL** (уже настроена)
- Конфигурация: `backend/config/settings/base.py:109-118`
- Параметры из `.env`: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`
- По умолчанию: `foodmind` / `foodmind` / `foodmind` @ `db:5432`

**Bot (aiogram 3):**
- Конфигурация БД: `bot/app/config.py:27-32`
- **Ботская БД**: PostgreSQL + SQLAlchemy (AsyncPG)
- Database URL: `postgresql+asyncpg://{user}:{password}@{host}:{port}/{dbname}`
- По умолчанию: `DB_NAME=foodmind` (указано использовать ту же БД!)
- **ВАЖНО**: Документация уже требует использовать одну БД, но код бота работает напрямую с БД через SQLAlchemy

### Структура данных:

**Backend Django models:**
1. **apps.users.Profile** - профиль пользователя (расширяет Django User)
2. **apps.telegram.TelegramUser** - связь Django User ↔ Telegram

**Bot SQLAlchemy models:**
1. **User** (`bot/app/models/user.py`) - пользователи бота
2. **SurveyAnswer** (`bot/app/models/survey.py:14-76`) - ответы на Personal Plan опрос
3. **Plan** (`bot/app/models/survey.py:78-115`) - AI-генерированные планы

### Уникальные таблицы бота:
- `users` - дублирует часть данных из backend
- `survey_answers` - ответы на Personal Plan опрос (уникальная сущность)
- `plans` - AI-генерированные планы (уникальная сущность)

### Места прямого доступа к БД в боте:
- `bot/app/services/database/session.py` - создание engine и session maker
- `bot/app/services/database/repository.py` - репозитории (UserRepository, SurveyRepository, PlanRepository)
- Хендлеры: `bot/app/handlers/survey/*.py` (11 файлов)
- `bot/app/services/events.py`

---

## ШАГ 2: ПЛАН ПЕРЕХОДА НА ЕДИНУЮ POSTGRES БД ✅

### Выбор главной БД
**PostgreSQL** (foodmind) - уже используется backend

### Django - уже на Postgres
Backend корректно настроен. Дополнительных действий не требуется.

### Новые Django-модели для ботских сущностей ✅

Созданы в `backend/apps/telegram/models.py`:

#### 1. PersonalPlanSurvey
Хранит ответы пользователя на опрос Personal Plan (аналог Bot.SurveyAnswer):
- Демографические данные: gender, age, height_cm, weight_kg, target_weight_kg, activity
- Дополнительно: training_level, body_goals (JSON), health_limitations (JSON)
- Типы фигуры: body_now_id/label/file, body_ideal_id/label/file
- Часовой пояс: timezone, utc_offset_minutes
- Метаданные: completed_at, created_at, updated_at

#### 2. PersonalPlan
AI-генерированные планы питания и тренировок (аналог Bot.Plan):
- user, survey (FK), ai_text, ai_model, prompt_version
- created_at

### Маппинг данных Bot → Django:

**Bot.User** → уже покрывается **TelegramUser + Profile**

**Bot.SurveyAnswer** → **PersonalPlanSurvey** (один-в-один маппинг)

**Bot.Plan** → **PersonalPlan** (один-в-один маппинг)

---

## ШАГ 3: РЕАЛИЗАЦИЯ - DJANGO МОДЕЛИ И МИГРАЦИИ

### 3.1. Созданные модели ✅

- ✅ `PersonalPlanSurvey` в `backend/apps/telegram/models.py`
- ✅ `PersonalPlan` в `backend/apps/telegram/models.py`

### 3.2. Созданные сериалайзеры ✅

В `backend/apps/telegram/serializers.py`:
- ✅ `PersonalPlanSurveySerializer` - для чтения/записи опросов
- ✅ `CreatePersonalPlanSurveySerializer` - для создания опроса от бота
- ✅ `PersonalPlanSerializer` - для чтения/записи планов
- ✅ `CreatePersonalPlanSerializer` - для создания плана от бота

### 3.3. Генерация миграций Django

```bash
cd backend
python manage.py makemigrations telegram
python manage.py migrate telegram
```

### 3.4. Management Command для миграции данных

Создать `backend/apps/telegram/management/commands/migrate_bot_data.py`:

```python
"""
Management команда для миграции данных из ботской БД в Django.
"""

import asyncio
from datetime import datetime
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from apps.telegram.models import TelegramUser, PersonalPlanSurvey, PersonalPlan


class Command(BaseCommand):
    help = 'Migrate bot database data to Django database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--bot-db-url',
            type=str,
            required=True,
            help='Bot database URL (e.g., postgresql+asyncpg://user:pass@host:port/dbname)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without saving to database'
        )

    def handle(self, *args, **options):
        bot_db_url = options['bot_db_url']
        dry_run = options['dry_run']

        self.stdout.write(f"Starting migration from {bot_db_url}")
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - no changes will be saved"))

        asyncio.run(self.migrate_data(bot_db_url, dry_run))

    async def migrate_data(self, bot_db_url: str, dry_run: bool):
        """Основная логика миграции."""

        # Подключаемся к ботской БД
        bot_engine = create_async_engine(bot_db_url, echo=False)
        BotSessionMaker = async_sessionmaker(bot_engine, class_=AsyncSession, expire_on_commit=False)

        async with BotSessionMaker() as bot_session:
            # Импортируем модели бота
            from app.models import User as BotUser, SurveyAnswer, Plan

            # 1. Мигрируем Users
            self.stdout.write("Migrating users...")
            result = await bot_session.execute(select(BotUser))
            bot_users = result.scalars().all()

            user_mapping = {}  # bot_user.id -> django_user.id

            for bot_user in bot_users:
                # Проверяем, есть ли уже такой пользователь
                try:
                    telegram_user = TelegramUser.objects.get(telegram_id=bot_user.tg_id)
                    django_user = telegram_user.user
                    self.stdout.write(f"  User {bot_user.tg_id} already exists (Django ID: {django_user.id})")
                except TelegramUser.DoesNotExist:
                    if not dry_run:
                        # Создаём Django User
                        django_user = User.objects.create_user(
                            username=f"tg_{bot_user.tg_id}",
                            first_name=bot_user.full_name or '',
                        )

                        # Создаём TelegramUser
                        telegram_user = TelegramUser.objects.create(
                            user=django_user,
                            telegram_id=bot_user.tg_id,
                            username=bot_user.username or '',
                            first_name=bot_user.full_name or '',
                        )

                        # Обновляем Profile
                        profile = django_user.profile
                        profile.telegram_id = bot_user.tg_id
                        profile.telegram_username = bot_user.username
                        profile.timezone = bot_user.tz
                        profile.save()

                        self.stdout.write(self.style.SUCCESS(
                            f"  Created user {bot_user.tg_id} (Django ID: {django_user.id})"
                        ))
                    else:
                        django_user = None
                        self.stdout.write(f"  [DRY RUN] Would create user {bot_user.tg_id}")

                if django_user:
                    user_mapping[bot_user.id] = django_user.id

            # 2. Мигрируем SurveyAnswers
            self.stdout.write("\nMigrating survey answers...")
            result = await bot_session.execute(select(SurveyAnswer))
            survey_answers = result.scalars().all()

            survey_mapping = {}  # bot_survey.id -> django_survey.id

            for bot_survey in survey_answers:
                django_user_id = user_mapping.get(bot_survey.user_id)
                if not django_user_id:
                    self.stdout.write(self.style.WARNING(
                        f"  Skipping survey {bot_survey.id}: user {bot_survey.user_id} not found"
                    ))
                    continue

                if not dry_run:
                    django_survey = PersonalPlanSurvey.objects.create(
                        user_id=django_user_id,
                        gender=bot_survey.gender,
                        age=bot_survey.age,
                        height_cm=bot_survey.height_cm,
                        weight_kg=bot_survey.weight_kg,
                        target_weight_kg=bot_survey.target_weight_kg,
                        activity=bot_survey.activity,
                        training_level=bot_survey.training_level,
                        body_goals=bot_survey.body_goals or [],
                        health_limitations=bot_survey.health_limitations or [],
                        body_now_id=bot_survey.body_now_id,
                        body_now_label=bot_survey.body_now_label,
                        body_now_file=bot_survey.body_now_file,
                        body_ideal_id=bot_survey.body_ideal_id,
                        body_ideal_label=bot_survey.body_ideal_label,
                        body_ideal_file=bot_survey.body_ideal_file,
                        timezone=bot_survey.tz,
                        utc_offset_minutes=bot_survey.utc_offset_minutes,
                        completed_at=bot_survey.completed_at,
                        created_at=bot_survey.created_at,
                    )

                    survey_mapping[bot_survey.id] = django_survey.id

                    self.stdout.write(self.style.SUCCESS(
                        f"  Migrated survey {bot_survey.id} -> {django_survey.id}"
                    ))
                else:
                    self.stdout.write(f"  [DRY RUN] Would migrate survey {bot_survey.id}")

            # 3. Мигрируем Plans
            self.stdout.write("\nMigrating plans...")
            result = await bot_session.execute(select(Plan))
            plans = result.scalars().all()

            for bot_plan in plans:
                django_user_id = user_mapping.get(bot_plan.user_id)
                if not django_user_id:
                    self.stdout.write(self.style.WARNING(
                        f"  Skipping plan {bot_plan.id}: user {bot_plan.user_id} not found"
                    ))
                    continue

                django_survey_id = survey_mapping.get(bot_plan.survey_answer_id) if bot_plan.survey_answer_id else None

                if not dry_run:
                    django_plan = PersonalPlan.objects.create(
                        user_id=django_user_id,
                        survey_id=django_survey_id,
                        ai_text=bot_plan.ai_text,
                        ai_model=bot_plan.ai_model,
                        prompt_version=bot_plan.prompt_version,
                        created_at=bot_plan.created_at,
                    )

                    self.stdout.write(self.style.SUCCESS(
                        f"  Migrated plan {bot_plan.id} -> {django_plan.id}"
                    ))
                else:
                    self.stdout.write(f"  [DRY RUN] Would migrate plan {bot_plan.id}")

        await bot_engine.dispose()

        self.stdout.write(self.style.SUCCESS("\nMigration completed successfully!"))
        self.stdout.write(f"  Users: {len(user_mapping)}")
        self.stdout.write(f"  Surveys: {len(survey_mapping)}")
        self.stdout.write(f"  Plans: migrated")
```

---

## ШАГ 4: ОТВЯЗКА БОТА ОТ ПРЯМОЙ РАБОТЫ С БД

### 4.1. Создание API endpoints в backend

Добавить в `backend/apps/telegram/views.py`:

```python
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.models import User
from .models import TelegramUser, PersonalPlanSurvey, PersonalPlan
from .serializers import (
    CreatePersonalPlanSurveySerializer,
    PersonalPlanSurveySerializer,
    CreatePersonalPlanSerializer,
    PersonalPlanSerializer,
)
from datetime import datetime, date


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
```

Добавить роуты в `backend/apps/telegram/urls.py`:

```python
urlpatterns = [
    # ... существующие роуты ...

    # Personal Plan API (для бота)
    path('users/get-or-create/', views.get_user_or_create, name='telegram-user-get-or-create'),
    path('personal-plan/survey/', views.create_survey, name='personal-plan-create-survey'),
    path('personal-plan/plan/', views.create_plan, name='personal-plan-create-plan'),
    path('personal-plan/count-today/', views.count_plans_today, name='personal-plan-count-today'),
]
```

### 4.2. Создание HTTP-клиента для бота

Создать `bot/app/services/backend_api.py`:

```python
"""
HTTP-клиент для взаимодействия с Django backend API.
"""

import logging
from typing import Any, Dict, Optional
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.config import settings


logger = logging.getLogger(__name__)


class BackendAPIClient:
    """Клиент для взаимодействия с Django backend API."""

    def __init__(self):
        self.base_url = settings.DJANGO_API_URL
        self.timeout = settings.DJANGO_API_TIMEOUT

        if not self.base_url:
            raise ValueError("DJANGO_API_URL not configured in settings")

    @retry(
        stop=stop_after_attempt(settings.DJANGO_RETRY_ATTEMPTS),
        wait=wait_exponential(
            multiplier=settings.DJANGO_RETRY_MULTIPLIER,
            min=settings.DJANGO_RETRY_MIN_WAIT,
            max=settings.DJANGO_RETRY_MAX_WAIT,
        ),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    )
    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Базовый метод для HTTP запросов с retry логикой.

        Args:
            method: HTTP метод (GET, POST, etc.)
            endpoint: API endpoint (без base_url)
            **kwargs: Параметры для httpx.request

        Returns:
            Распарсенный JSON ответ

        Raises:
            httpx.HTTPStatusError: При HTTP ошибках
            httpx.TimeoutException: При таймауте
        """
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            logger.debug(f"[BackendAPI] {method} {url}")

            response = await client.request(method, url, **kwargs)
            response.raise_for_status()

            return response.json()

    async def get_or_create_user(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        full_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Получить или создать пользователя.

        Args:
            telegram_id: Telegram ID пользователя
            username: Username (опционально)
            full_name: Полное имя (опционально)

        Returns:
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
        params = {"telegram_id": telegram_id}
        if username:
            params["username"] = username
        if full_name:
            params["full_name"] = full_name

        return await self._request("GET", "telegram/users/get-or-create/", params=params)

    async def create_survey(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Создать ответ на опрос Personal Plan.

        Args:
            data: Данные опроса (должен содержать telegram_id и все поля опроса)

        Returns:
            Созданный опрос
        """
        return await self._request("POST", "telegram/personal-plan/survey/", json=data)

    async def create_plan(
        self,
        telegram_id: int,
        ai_text: str,
        survey_id: Optional[int] = None,
        ai_model: Optional[str] = None,
        prompt_version: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Создать Personal Plan.

        Args:
            telegram_id: Telegram ID пользователя
            ai_text: Текст плана от AI
            survey_id: ID опроса (опционально)
            ai_model: Модель AI (опционально)
            prompt_version: Версия промпта (опционально)

        Returns:
            Созданный план
        """
        data = {
            "telegram_id": telegram_id,
            "ai_text": ai_text,
        }

        if survey_id:
            data["survey_id"] = survey_id
        if ai_model:
            data["ai_model"] = ai_model
        if prompt_version:
            data["prompt_version"] = prompt_version

        return await self._request("POST", "telegram/personal-plan/plan/", json=data)

    async def count_plans_today(self, telegram_id: int) -> Dict[str, Any]:
        """
        Подсчитать количество планов пользователя за сегодня.

        Args:
            telegram_id: Telegram ID пользователя

        Returns:
            {
                "count": 2,
                "limit": 3,
                "can_create": true
            }
        """
        return await self._request(
            "GET",
            "telegram/personal-plan/count-today/",
            params={"telegram_id": telegram_id}
        )


# Глобальный экземпляр клиента
backend_api = BackendAPIClient()
```

### 4.3. Переписать хендлеры бота

Пример для `bot/app/handlers/survey/confirmation.py`:

```python
# СТАРЫЙ КОД (с прямым доступом к БД):
# from app.services.database.repository import SurveyRepository, PlanRepository
# ...
# async with get_session() as session:
#     survey = await SurveyRepository.create_survey_answer(session, user.id, state_data)
#     plan = await PlanRepository.create_plan(...)

# НОВЫЙ КОД (через API):
from app.services.backend_api import backend_api

# ...

# Создаём опрос через API
survey_data = {
    "telegram_id": message.from_user.id,
    "gender": state_data["gender"],
    "age": state_data["age"],
    "height_cm": state_data["height_cm"],
    "weight_kg": state_data["weight_kg"],
    "target_weight_kg": state_data.get("target_weight_kg"),
    "activity": state_data["activity"],
    "training_level": state_data.get("training_level"),
    "body_goals": state_data.get("body_goals", []),
    "health_limitations": state_data.get("health_limitations", []),
    "body_now_id": state_data["body_now_id"],
    "body_now_label": state_data.get("body_now_label"),
    "body_now_file": state_data["body_now_file"],
    "body_ideal_id": state_data["body_ideal_id"],
    "body_ideal_label": state_data.get("body_ideal_label"),
    "body_ideal_file": state_data["body_ideal_file"],
    "timezone": state_data["tz"],
    "utc_offset_minutes": state_data["utc_offset_minutes"],
}

try:
    survey = await backend_api.create_survey(survey_data)
    survey_id = survey["id"]

    # Генерируем AI план (существующая логика)
    ai_text = await generate_plan_with_ai(...)

    # Сохраняем план через API
    plan = await backend_api.create_plan(
        telegram_id=message.from_user.id,
        survey_id=survey_id,
        ai_text=ai_text,
        ai_model=settings.OPENROUTER_MODEL,
        prompt_version=settings.AI_PROMPT_VERSION,
    )

except httpx.HTTPError as e:
    logger.error(f"Failed to save survey/plan: {e}")
    await message.answer("Произошла ошибка при сохранении данных. Попробуйте позже.")
    return
```

Аналогично переписать все хендлеры в:
- `bot/app/handlers/survey/*.py`
- Заменить все вызовы `UserRepository`, `SurveyRepository`, `PlanRepository` на вызовы `backend_api`

---

## ШАГ 5: ЧИСТКА И ФИКСАЦИЯ

### 5.1. Удалить устаревший код БД в боте

После переписания всех хендлеров:

1. **Удалить или закомментировать**:
   - `bot/app/services/database/session.py`
   - `bot/app/services/database/repository.py`
   - `bot/app/models/` (user.py, survey.py) - оставить только для референса

2. **Удалить из `bot/app/services/events.py`**:
   ```python
   # УДАЛИТЬ:
   # from app.services.database.session import init_db, close_db
   # await init_db()  # при старте
   # await close_db()  # при остановке
   ```

3. **Удалить зависимости** из `bot/requirements.txt` (если больше не нужны):
   ```
   # УДАЛИТЬ (если не используются):
   # sqlalchemy
   # alembic
   # asyncpg
   ```

4. **Удалить конфигурацию БД** из `bot/app/config.py`:
   ```python
   # УДАЛИТЬ или закомментировать:
   # DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
   # @property
   # def database_url(self) -> str:
   #     ...
   ```

5. **Пометить Alembic миграции как legacy**:
   - Добавить `bot/alembic/versions/README.md`:
     ```markdown
     # LEGACY MIGRATIONS

     These migrations are no longer used. The bot now uses Django backend API instead of direct database access.

     For historical reference only.
     ```

### 5.2. Обновить документацию

Создать или обновить `README.md` в корне проекта:

```markdown
# Fitness App

## Архитектура

Проект состоит из трёх частей:
- `/backend` — Django + DRF (главный API и единственный источник бизнес-логики)
- `/bot` — Telegram-бот на aiogram 3 (Python)
- `/frontend` — веб/мини-ап (опционально)

### База данных

**ВАЖНО**: Проект использует ЕДИНУЮ БД PostgreSQL.

- БД: PostgreSQL (схема управляется Django)
- Все данные хранятся в главной БД `foodmind`
- Бот НЕ работает с БД напрямую - только через REST API backend

### Конфигурация

Главная БД настраивается через переменные окружения:
```env
POSTGRES_DB=foodmind
POSTGRES_USER=foodmind
POSTGRES_PASSWORD=supersecret
POSTGRES_HOST=db
POSTGRES_PORT=5432
```

Бот использует те же переменные только для совместимости legacy конфигов, но НЕ подключается к БД напрямую.

## API endpoints для бота

Backend предоставляет следующие endpoints для бота:

- `GET /api/v1/telegram/users/get-or-create/` - получить или создать пользователя
- `POST /api/v1/telegram/personal-plan/survey/` - создать опрос Personal Plan
- `POST /api/v1/telegram/personal-plan/plan/` - создать AI план
- `GET /api/v1/telegram/personal-plan/count-today/` - подсчитать планы за день

## Deployment

1. Применить миграции Django:
   ```bash
   cd backend
   python manage.py migrate
   ```

2. (Опционально) Мигрировать данные из старой ботской БД:
   ```bash
   python manage.py migrate_bot_data --bot-db-url="postgresql+asyncpg://user:pass@host:port/dbname"
   ```

3. Запустить backend:
   ```bash
   python manage.py runserver
   ```

4. Запустить бота:
   ```bash
   cd bot
   python main.py
   ```
```

---

## РЕЗЮМЕ ПРОДЕЛАННЫХ ИЗМЕНЕНИЙ

### ✅ Завершено:

1. **Аудит БД и доступа к данным**
   - Проанализированы конфигурации backend и bot
   - Определены уникальные таблицы бота
   - Найдены все места прямого доступа к БД

2. **Создан план перехода на единую Postgres БД**
   - Backend уже на Postgres
   - Определён маппинг данных Bot → Django

3. **Созданы Django-модели**
   - ✅ `PersonalPlanSurvey` в `backend/apps/telegram/models.py`
   - ✅ `PersonalPlan` в `backend/apps/telegram/models.py`

4. **Созданы сериалайзеры**
   - ✅ `PersonalPlanSurveySerializer`
   - ✅ `CreatePersonalPlanSurveySerializer`
   - ✅ `PersonalPlanSerializer`
   - ✅ `CreatePersonalPlanSerializer`

5. **Подготовлен план дальнейшей работы**
   - Примеры API endpoints
   - Примеры HTTP-клиента для бота
   - Пример переписывания хендлеров
   - План чистки legacy кода

---

## РУЧНЫЕ ШАГИ ДЛЯ ВАС

### Шаг 1: Применить миграции Django

```bash
cd backend
python manage.py makemigrations telegram
python manage.py migrate telegram
```

### Шаг 2: Добавить API views и routes

1. Добавить функции из раздела 4.1 в `backend/apps/telegram/views.py`
2. Добавить роуты из раздела 4.1 в `backend/apps/telegram/urls.py`

### Шаг 3: Создать HTTP-клиент в боте

1. Создать `bot/app/services/backend_api.py` с кодом из раздела 4.2

### Шаг 4: Переписать хендлеры бота

1. Заменить все обращения к БД в `bot/app/handlers/survey/*.py` на вызовы `backend_api`
2. Использовать пример из раздела 4.3

### Шаг 5: (Опционально) Мигрировать данные

1. Создать `backend/apps/telegram/management/commands/migrate_bot_data.py`
2. Запустить (только если у вас есть данные в старой ботской БД):
   ```bash
   python manage.py migrate_bot_data \
     --bot-db-url="postgresql+asyncpg://foodmind:foodmind@localhost:5432/calorie_bot_db" \
     --dry-run  # Сначала dry-run

   python manage.py migrate_bot_data \
     --bot-db-url="postgresql+asyncpg://foodmind:foodmind@localhost:5432/calorie_bot_db"  # Реальная миграция
   ```

### Шаг 6: Удалить устаревший код

1. Следовать инструкциям из раздела 5.1
2. Удалить/закомментировать прямой доступ к БД

### Шаг 7: Обновить документацию

1. Обновить README.md согласно разделу 5.2

### Шаг 8: Тестирование

1. Запустить backend: `python manage.py runserver`
2. Запустить бота: `python bot/main.py`
3. Протестировать флоу Personal Plan в боте
4. Убедиться, что данные сохраняются в Django БД

---

## Контрольный чеклист

- [ ] Применены миграции Django (`makemigrations` + `migrate`)
- [ ] Добавлены API endpoints в backend (views + urls)
- [ ] Создан HTTP-клиент `bot/app/services/backend_api.py`
- [ ] Переписаны хендлеры бота на использование API
- [ ] Удалён код прямого доступа к БД в боте
- [ ] (Опционально) Мигрированы данные из старой БД
- [ ] Обновлена документация
- [ ] Протестирован флоу Personal Plan
- [ ] Перезапущены backend + bot

---

**Дата создания плана**: 2025-01-26
**Статус**: Готов к выполнению
