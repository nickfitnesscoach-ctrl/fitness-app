# Реализация API интеграции Backend ↔ Bot - ЗАВЕРШЕНА

## Выполненные задачи

### 1. Backend (Django)

#### Добавлены API endpoints в [backend/apps/telegram/views.py](backend/apps/telegram/views.py)

Реализованы 4 новых view функции (строки 786-1069):

- `get_user_or_create(request)` - Получение или создание пользователя по telegram_id
- `create_survey(request)` - Создание опроса Personal Plan
- `create_plan(request)` - Создание AI-генерированного плана (с проверкой лимита 3 плана/день)
- `count_plans_today(request)` - Получение количества планов за сегодня

#### Добавлены роуты в [backend/apps/telegram/urls.py](backend/apps/telegram/urls.py)

Новые URL patterns (строки 36-39):

```python
path('users/get-or-create/', views.get_user_or_create, name='telegram-user-get-or-create'),
path('personal-plan/survey/', views.create_survey, name='personal-plan-create-survey'),
path('personal-plan/plan/', views.create_plan, name='personal-plan-create-plan'),
path('personal-plan/count-today/', views.count_plans_today, name='personal-plan-count-today'),
```

#### Созданы unit-тесты в [backend/apps/telegram/tests.py](backend/apps/telegram/tests.py)

Полный набор тестов (222 строки, 11 тестовых методов):

- Тесты get_user_or_create (существующий/новый пользователь, отсутствующий telegram_id)
- Тесты create_survey (валидные/невалидные данные)
- Тесты create_plan (создание, user not found, daily limit)
- Тесты count_plans_today (подсчёт, user not found, missing telegram_id)

### 2. Bot (Telegram)

#### Создан HTTP клиент в [bot/app/services/backend_api.py](bot/app/services/backend_api.py)

Новый файл с классом `BackendAPIClient`:

- Async HTTP запросы через httpx
- Retry логика с exponential backoff (tenacity)
- 4 метода для работы с Backend API:
  - `get_or_create_user(telegram_id, username, full_name)`
  - `create_survey(telegram_id, gender, age, ...)`
  - `create_plan(telegram_id, ai_text, survey_id, ai_model, prompt_version)`
  - `count_plans_today(telegram_id)`
- Singleton функция `get_backend_api()` для получения глобального экземпляра
- Подробное логирование всех запросов и ошибок
- Custom exception `BackendAPIError` для обработки ошибок API

#### Обновлена конфигурация в [bot/app/config.py](bot/app/config.py)

Уже присутствовали необходимые настройки (строки 73-81):

- `DJANGO_API_URL` - базовый URL Django API
- `DJANGO_RETRY_ATTEMPTS` - количество попыток
- `DJANGO_RETRY_MIN_WAIT` / `DJANGO_RETRY_MAX_WAIT` - задержки между попытками
- `DJANGO_RETRY_MULTIPLIER` - множитель для exponential backoff
- `DJANGO_API_TIMEOUT` - таймаут запросов

#### Переписаны хендлеры Personal Plan в [bot/app/handlers/survey/confirmation.py](bot/app/handlers/survey/confirmation.py)

Заменены прямые обращения к БД на вызовы Backend API:

**Изменения в импортах:**
- Удалено: `from app.services.database import PlanRepository, SurveyRepository, UserRepository, async_session_maker`
- Удалено: `from app.services.django_integration import send_test_results_to_django`
- Добавлено: `from app.services.backend_api import BackendAPIError, get_backend_api`

**Изменения в функции `confirm_and_generate` (строки 52-72):**
- Rate limit проверка через `backend_api.count_plans_today(user_id)`
- Обработка ошибок через `BackendAPIError`

**Изменения в сохранении данных (строки 165-223):**
- Вызов `backend_api.get_or_create_user(...)` вместо `UserRepository.get_or_create`
- Вызов `backend_api.create_survey(...)` вместо `SurveyRepository.create_survey_answer`
- Вызов `backend_api.create_plan(...)` вместо `PlanRepository.create_plan`
- Удалён вызов `send_test_results_to_django` (теперь данные сохраняются напрямую через API)
- Обработка ошибок через `BackendAPIError`

## Что нужно сделать вручную

### 1. Применить миграции Django

```bash
cd backend
python manage.py makemigrations telegram
python manage.py migrate
```

### 2. Настроить переменные окружения

#### Backend (.env)
Убедитесь, что настроена PostgreSQL БД:
```env
POSTGRES_DB=foodmind
POSTGRES_USER=foodmind
POSTGRES_PASSWORD=your_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

#### Bot (.env)
Добавьте URL Django API:
```env
# Для локальной разработки
DJANGO_API_URL=http://localhost:8000/api/v1

# Для Docker Compose (если bot и backend в одной сети)
DJANGO_API_URL=http://backend:8000/api/v1

# Для production
DJANGO_API_URL=https://eatfit24.ru/api/v1
```

### 3. Запустить тесты Backend

```bash
cd backend
python manage.py test apps.telegram.tests.PersonalPlanAPITestCase
```

### 4. Перезапустить сервисы

```bash
# Backend
cd backend
python manage.py runserver

# Bot
cd bot
python -m app.bot
```

## Проверка работоспособности

### 1. Проверка Backend API

```bash
# Тест get_user_or_create
curl "http://localhost:8000/api/v1/telegram/users/get-or-create/?telegram_id=123456789&username=testuser&full_name=Test User"

# Тест count_plans_today
curl "http://localhost:8000/api/v1/telegram/personal-plan/count-today/?telegram_id=123456789"
```

### 2. Проверка Bot

1. Запустите бота
2. Пройдите опрос Personal Plan до конца
3. Подтвердите данные и дождитесь генерации плана
4. Проверьте логи бота на наличие успешных запросов к Backend API:
   ```
   [BackendAPI] GET http://localhost:8000/api/v1/telegram/personal-plan/count-today/ | params={'telegram_id': 123456789}
   [BackendAPI] Успешный ответ: {'count': 0, 'limit': 3, 'can_create': True}
   ```

### 3. Проверка в Django Admin

1. Откройте Django Admin: http://localhost:8000/admin/
2. Перейдите в Telegram → Personal Plan Surveys
3. Убедитесь, что опросы сохраняются
4. Перейдите в Telegram → Personal Plans
5. Убедитесь, что планы сохраняются с привязкой к опросам

## Что осталось без изменений

Старый код bot с прямым доступом к БД **НЕ УДАЛЁН**, как и было запрошено:

- [bot/app/services/database/](bot/app/services/database/) - все модели и репозитории SQLAlchemy
- Миграции Alembic в bot/
- Настройки БД в bot/app/config.py

Эти файлы можно удалить позже, когда убедитесь, что новая архитектура работает корректно.

## Архитектура после изменений

```
┌─────────────────────┐
│   Telegram Bot      │
│   (aiogram 3)       │
└──────────┬──────────┘
           │
           │ HTTP API (httpx + tenacity)
           │
           ▼
┌─────────────────────┐
│  Django Backend     │
│  (REST API)         │
└──────────┬──────────┘
           │
           │ ORM
           │
           ▼
┌─────────────────────┐
│   PostgreSQL DB     │
│   (foodmind)        │
└─────────────────────┘
```

## Ключевые преимущества

1. **Единая БД** - PostgreSQL управляется только Django
2. **Единая бизнес-логика** - все валидации и ограничения в Django
3. **Изоляция** - бот не знает о структуре БД, работает только через API
4. **Отказоустойчивость** - retry логика с exponential backoff
5. **Тестируемость** - полный набор unit-тестов для API
6. **Логирование** - подробные логи всех API запросов

## Файлы, изменённые в этой реализации

### Backend
- [backend/apps/telegram/views.py](backend/apps/telegram/views.py) - добавлено 284 строки
- [backend/apps/telegram/urls.py](backend/apps/telegram/urls.py) - добавлено 4 строки
- [backend/apps/telegram/tests.py](backend/apps/telegram/tests.py) - создан файл (222 строки)
- [backend/apps/telegram/serializers.py](backend/apps/telegram/serializers.py) - уже существовали нужные сериализаторы
- [backend/apps/telegram/models.py](backend/apps/telegram/models.py) - уже существовали нужные модели

### Bot
- [bot/app/services/backend_api.py](bot/app/services/backend_api.py) - создан новый файл (335 строк)
- [bot/app/handlers/survey/confirmation.py](bot/app/handlers/survey/confirmation.py) - переписан с БД на API (изменено ~60 строк)
- [bot/app/config.py](bot/app/config.py) - уже содержал нужные настройки
- [bot/requirements.txt](bot/requirements.txt) - уже содержал httpx и tenacity

### Документация
- [REFACTORING_PLAN.md](REFACTORING_PLAN.md) - создан ранее
- [IMPLEMENTATION_COMPLETE.md](IMPLEMENTATION_COMPLETE.md) - этот файл

---

Готово! Архитектура успешно рефакторена с прямого доступа к БД на REST API взаимодействие.
