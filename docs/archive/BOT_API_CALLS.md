# EatFit24 Bot API Calls

> **Клиент**: `BackendAPIClient` в `app/services/backend_api.py`  
> **Библиотека**: `httpx` (async)  
> **Retry**: `tenacity` (3 попытки, exponential backoff)

---

## Конфигурация

| Параметр | ENV | Default | Описание |
|----------|-----|---------|----------|
| Base URL | `DJANGO_API_URL` | `http://backend:8000/api/v1` | Базовый URL API |
| Timeout | `DJANGO_API_TIMEOUT` | 30 сек | Таймаут запроса |
| Retry attempts | `DJANGO_RETRY_ATTEMPTS` | 3 | Количество попыток |
| Min wait | `DJANGO_RETRY_MIN_WAIT` | 1 сек | Мин. задержка |
| Max wait | `DJANGO_RETRY_MAX_WAIT` | 8 сек | Макс. задержка |
| Multiplier | `DJANGO_RETRY_MULTIPLIER` | 2 | Множитель backoff |

---

## Список API вызовов

### 1. GET `/telegram/users/get-or-create/`

**Назначение**: Создать или получить пользователя по Telegram ID

| Параметр | Расположение | Тип | Описание |
|----------|--------------|-----|----------|
| `telegram_id` | query | int | Telegram user ID |
| `username` | query | str? | Telegram username |
| `full_name` | query | str? | Полное имя |

**Пример запроса**:
```http
GET /api/v1/telegram/users/get-or-create/?telegram_id=123456&username=johndoe&full_name=John%20Doe
```

**Ответ (200 OK)**:
```json
{
  "telegram_id": 123456,
  "username": "johndoe",
  "first_name": "John",
  "last_name": "Doe",
  "display_name": "John Doe",
  "created": false
}
```

**Файл**: `backend_api.py`  
**Строка**: 143-173

---

### 2. POST `/telegram/personal-plan/survey/`

**Назначение**: Сохранить ответы опроса Personal Plan

**Тело запроса (JSON)**:
```json
{
  "telegram_id": 123456,
  "gender": "male",
  "age": 30,
  "height_cm": 180,
  "weight_kg": 85.5,
  "target_weight_kg": 80.0,
  "activity": "moderate",
  "training_level": "intermediate",
  "body_goals": ["lose_fat", "build_muscle"],
  "health_limitations": ["bad_knees"],
  "body_now_id": 3,
  "body_now_label": "Average",
  "body_now_file": "male/now/3.png",
  "body_ideal_id": 5,
  "body_ideal_label": "Athletic",
  "body_ideal_file": "male/ideal/5.png",
  "timezone": "Europe/Moscow",
  "utc_offset_minutes": 180
}
```

**Обязательные поля**:
- `telegram_id`, `gender`, `age`, `height_cm`, `weight_kg`, `activity`
- `body_now_id`, `body_now_file`, `body_ideal_id`, `body_ideal_file`
- `timezone`, `utc_offset_minutes`

**Ответ (201 Created)**:
```json
{
  "id": 42,
  "telegram_id": 123456,
  "gender": "male",
  "age": 30,
  "created_at": "2025-12-24T15:30:00Z"
}
```

**Файл**: `backend_api.py`  
**Строка**: 175-251

---

### 3. POST `/telegram/personal-plan/plan/`

**Назначение**: Сохранить сгенерированный AI план

**Тело запроса (JSON)**:
```json
{
  "telegram_id": 123456,
  "survey_id": 42,
  "ai_text": "# Ваш персональный план\n\n## Питание\n...",
  "ai_model": "meta-llama/llama-3.1-70b-instruct",
  "prompt_version": "v1.0"
}
```

**Обязательные поля**:
- `telegram_id`, `ai_text`

**Опциональные поля**:
- `survey_id`, `ai_model`, `prompt_version`

**Ответ (201 Created)**:
```json
{
  "id": 123,
  "telegram_id": 123456,
  "survey_id": 42,
  "created_at": "2025-12-24T15:35:00Z"
}
```

**Ошибка (429 Too Many Requests)**:
```json
{
  "error": "Rate limit exceeded",
  "detail": "Maximum 3 plans per day"
}
```

**Файл**: `backend_api.py`  
**Строка**: 253-289

---

### 4. GET `/telegram/personal-plan/count-today/`

**Назначение**: Проверить количество планов, созданных сегодня

| Параметр | Расположение | Тип | Описание |
|----------|--------------|-----|----------|
| `telegram_id` | query | int | Telegram user ID |

**Пример запроса**:
```http
GET /api/v1/telegram/personal-plan/count-today/?telegram_id=123456
```

**Ответ (200 OK)**:
```json
{
  "count": 1,
  "limit": 3,
  "can_create": true
}
```

**Файл**: `backend_api.py`  
**Строка**: 291-306

---

## Legacy API (НЕ ИСПОЛЬЗУЕТСЯ)

### POST `/telegram/save-test/`

**Статус**: ⚠️ LEGACY — код существует, но не вызывается

**Файл**: `django_integration.py:150`

**Тело запроса**:
```json
{
  "telegram_id": 123456,
  "first_name": "John",
  "last_name": "Doe",
  "username": "johndoe",
  "answers": {
    "age": 30,
    "gender": "male",
    "weight": 85.5,
    "height": 180,
    "activity_level": "medium",
    "goal": "weight_loss",
    "target_weight": 80.0,
    "timezone": "Europe/Moscow",
    "training_level": "intermediate",
    "goals": ["lose_fat"],
    "health_restrictions": ["bad_knees"],
    "current_body_type": 3,
    "ideal_body_type": 5
  }
}
```

**Рекомендация**: Удалить `django_integration.py` при cleanup SQLAlchemy.

---

## Места вызовов

| API Endpoint | Файл вызова | Строка | Функция |
|--------------|-------------|--------|---------|
| `users/get-or-create/` | `confirmation.py` | 170 | `confirm_and_generate` |
| `personal-plan/survey/` | `confirmation.py` | 177 | `confirm_and_generate` |
| `personal-plan/plan/` | `confirmation.py` | 199 | `confirm_and_generate` |
| `personal-plan/count-today/` | `confirmation.py` | 54 | `confirm_and_generate` |

Все 4 вызова происходят в одном хендлере `confirm_and_generate()` при подтверждении опроса.

---

## Обработка ошибок

| Код | Действие |
|-----|----------|
| 200-299 | Успех, вернуть JSON |
| 429 | Retry (до 3 раз) |
| 502, 503, 504 | Retry (до 3 раз) |
| 400-499 (кроме 429) | Raise `BackendAPIError` |
| Network error | Retry, затем `BackendAPIError` |
| Timeout | Retry, затем `BackendAPIError` |

При ошибке `count_plans_today` — продолжить генерацию (fail-open).  
При ошибке сохранения — показать план пользователю с предупреждением.
