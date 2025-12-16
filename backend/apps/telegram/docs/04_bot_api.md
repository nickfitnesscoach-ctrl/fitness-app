# Telegram Bot API

| | |
|---|---|
| **Статус** | production-ready |
| **Владелец** | `apps/telegram/bot/` |
| **Проверено** | 2024-12-16 |
| **Правило** | Меняешь код в `apps/telegram/*` → обнови docs |

---

## Quick Reference: Эндпоинты

| Endpoint | Method | Secret | Purpose | Main Errors |
|----------|--------|--------|---------|-------------|
| `/save-test/` | POST | ✅ | Сохранить AI-тест | 400 (validation), 403 (secret) |
| `/users/get-or-create/` | GET | ✅ | Найти/создать user | 400 (no telegram_id), 403 |
| `/personal-plan/survey/` | POST | ✅ | Создать анкету | 400, 403, 404 (user) |
| `/personal-plan/plan/` | POST | ✅ | Сохранить AI-план | 400, 403, 404, **429** (limit) |
| `/personal-plan/count-today/` | GET | ✅ | Счётчик планов | 400, 403 |
| `/invite-link/` | GET | ❌ | Ссылка на бота | — (публичный) |

---

## Назначение

Bot API — это набор эндпоинтов, которые использует Telegram-бот для:
- Создания/обновления пользователей
- Сохранения результатов AI-теста (лид-магнит)
- Создания анкет и AI-планов Personal Plan
- Получения служебной информации

> [!IMPORTANT]
> Bot API — это **write-зона**. Эндпоинты создают и изменяют записи в БД, поэтому они защищены секретным ключом.

---

## Защита: X-Bot-Secret

### Как это работает

Бот при каждом запросе передаёт секретный ключ в заголовке:

```
X-Bot-Secret: your-super-secret-key
```

Backend сравнивает его с `settings.TELEGRAM_BOT_API_SECRET`:

```python
def _bot_secret_ok(request) -> bool:
    expected = settings.TELEGRAM_BOT_API_SECRET
    if not expected:
        # В DEV (DEBUG=True) без секрета — норм
        # В PROD — это ошибка конфигурации
        return settings.DEBUG
    
    provided = request.headers.get("X-Bot-Secret")
    return provided == expected
```

### Почему не initData

| Аспект | initData | X-Bot-Secret |
|--------|----------|--------------|
| Кто использует | Mini App (пользователь) | Бот (сервис) |
| Что содержит | Данные пользователя | Просто секрет |
| TTL | 24 часа | Бессрочно |
| Генерация | Telegram сервер | Вы (при деплое) |

Бот — это отдельный сервис, а не пользователь в Telegram. Он не имеет `initData`.

---

## Эндпоинты

### POST `/api/v1/telegram/save-test/`

**Назначение:** Сохранение результатов AI-теста (лид-магнит).

**Кто вызывает:** Telegram-бот после прохождения теста пользователем.

**Требует:** `X-Bot-Secret`

**Тело запроса:**

```json
{
  "telegram_id": 123456789,
  "first_name": "Иван",
  "last_name": "Петров",
  "username": "ivan_petrov",
  "answers": {
    "gender": "male",
    "age": 30,
    "weight": 80,
    "height": 175,
    "goal": "weight_loss",
    "activity_level": "medium",
    "target_weight": 70,
    "training_level": "beginner",
    "goals": ["lose_fat", "build_muscle"],
    "health_restrictions": [],
    "current_body_type": "endomorph",
    "ideal_body_type": "mesomorph"
  }
}
```

**Что происходит:**

1. Создаётся/обновляется `TelegramUser`
2. Обновляется `Profile` данными из теста
3. Устанавливается `ai_test_completed = True`
4. Сохраняются `ai_test_answers`
5. Пересчитывается `DailyGoal` (КБЖУ)
6. Сохраняются рекомендации в `TelegramUser.recommended_*`

**Ответ:**

```json
{
  "status": "success",
  "user_id": 42,
  "message": "Данные теста сохранены",
  "created": false
}
```

**Ошибки:**

| Код | Причина |
|-----|---------|
| 400 | Невалидные данные (telegram_id <= 0, answers не dict) |
| 403 | Неверный или отсутствующий X-Bot-Secret |
| 500 | Внутренняя ошибка сервера |

---

### GET `/api/v1/telegram/users/get-or-create/`

**Назначение:** Получить существующего пользователя или создать нового.

**Кто вызывает:** Telegram-бот при первом контакте с пользователем.

**Требует:** `X-Bot-Secret`

**Query параметры:**

| Параметр | Обязательный | Описание |
|----------|--------------|----------|
| `telegram_id` | Да | Telegram ID пользователя |
| `username` | Нет | @username |
| `full_name` | Нет | Полное имя |

**Пример:**

```
GET /api/v1/telegram/users/get-or-create/?telegram_id=123456789&username=ivan
```

**Ответ:**

```json
{
  "id": 15,
  "user_id": 42,
  "telegram_id": 123456789,
  "username": "ivan",
  "first_name": "Ivan",
  "last_name": "",
  "created": false
}
```

---

### POST `/api/v1/telegram/personal-plan/survey/`

**Назначение:** Создать анкету Personal Plan.

**Кто вызывает:** Telegram-бот после заполнения анкеты пользователем.

**Требует:** `X-Bot-Secret`

**Тело запроса:**

```json
{
  "telegram_id": 123456789,
  "gender": "male",
  "age": 30,
  "height_cm": 175,
  "weight_kg": 80.5,
  "target_weight_kg": 70.0,
  "activity": "moderate",
  "training_level": "intermediate",
  "body_goals": ["lose_fat", "build_muscle"],
  "health_limitations": ["back_pain"],
  "body_now_id": 3,
  "body_now_label": "Эндоморф",
  "body_now_file": "body_type_3.png",
  "body_ideal_id": 2,
  "body_ideal_label": "Мезоморф",
  "body_ideal_file": "body_type_2.png",
  "timezone": "Europe/Moscow",
  "utc_offset_minutes": 180
}
```

**Валидация:**

| Поле | Ограничения |
|------|-------------|
| `telegram_id` | > 0 |
| `gender` | "male" или "female" |
| `age` | 14-80 |
| `height_cm` | 120-250 |
| `weight_kg` | 30-300, 2 десятичных знака |
| `activity` | sedentary/light/moderate/active/very_active |
| `utc_offset_minutes` | -840 до 840 |

**Ответ:** Созданный `PersonalPlanSurvey` с ID и timestamp'ами.

---

### POST `/api/v1/telegram/personal-plan/plan/`

**Назначение:** Сохранить сгенерированный AI-план.

**Кто вызывает:** Telegram-бот после генерации плана через AI.

**Требует:** `X-Bot-Secret`

**Тело запроса:**

```json
{
  "telegram_id": 123456789,
  "survey_id": 15,
  "ai_text": "Персональный план питания для Ивана...\n\n## Рекомендации...",
  "ai_model": "gpt-4-turbo",
  "prompt_version": "v2.1"
}
```

**Ограничения:**

- **Лимит планов в день:** По умолчанию 3 (`PERSONAL_PLAN_DAILY_LIMIT`)
- При превышении лимита — `429 Too Many Requests`

**Ответ:** Созданный `PersonalPlan` с ID.

**Ошибки:**

| Код | Причина |
|-----|---------|
| 400 | Невалидные данные |
| 403 | Неверный X-Bot-Secret |
| 404 | Пользователь или survey не найден |
| 429 | Превышен дневной лимит планов |

---

### GET `/api/v1/telegram/personal-plan/count-today/`

**Назначение:** Узнать сколько планов создано сегодня.

**Кто вызывает:** Telegram-бот перед генерацией нового плана.

**Требует:** `X-Bot-Secret`

**Query параметры:**

| Параметр | Обязательный | Описание |
|----------|--------------|----------|
| `telegram_id` | Да | Telegram ID пользователя |

**Ответ:**

```json
{
  "count": 2,
  "limit": 3,
  "can_create": true
}
```

---

### GET `/api/v1/telegram/invite-link/`

**Назначение:** Получить ссылку-приглашение на бота.

**Кто вызывает:** Frontend или любой внешний сервис.

**Требует:** **Ничего** (публичный эндпоинт)

**Ответ:**

```json
{
  "link": "https://t.me/eatfit24_bot?start=invite"
}
```

> [!NOTE]
> Это единственный публичный эндпоинт в Bot API. Он read-only и не требует защиты.

---

## Примеры интеграции

### Python (бот на aiogram/python-telegram-bot)

```python
import aiohttp

BOT_SECRET = "your-super-secret-key"
API_BASE = "https://your-backend.com/api/v1/telegram"

async def save_test_results(telegram_id: int, answers: dict):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{API_BASE}/save-test/",
            json={
                "telegram_id": telegram_id,
                "answers": answers,
            },
            headers={"X-Bot-Secret": BOT_SECRET},
        ) as resp:
            return await resp.json()
```

### Обработка ошибок

```python
async def create_plan_safe(telegram_id: int, survey_id: int, ai_text: str):
    # Сначала проверяем лимит
    async with session.get(
        f"{API_BASE}/personal-plan/count-today/",
        params={"telegram_id": telegram_id},
        headers={"X-Bot-Secret": BOT_SECRET},
    ) as resp:
        data = await resp.json()
        if not data.get("can_create"):
            return {"error": "Daily limit reached"}
    
    # Создаём план
    async with session.post(
        f"{API_BASE}/personal-plan/plan/",
        json={
            "telegram_id": telegram_id,
            "survey_id": survey_id,
            "ai_text": ai_text,
        },
        headers={"X-Bot-Secret": BOT_SECRET},
    ) as resp:
        if resp.status == 429:
            return {"error": "Daily limit reached"}
        return await resp.json()
```

---

## Конфигурация

### Переменные окружения

```bash
# .env
TELEGRAM_BOT_API_SECRET=super-secret-random-string-32-chars
TELEGRAM_BOT_USERNAME=eatfit24_bot
PERSONAL_PLAN_DAILY_LIMIT=3
```

### settings.py

```python
TELEGRAM_BOT_API_SECRET = env("TELEGRAM_BOT_API_SECRET", default=None)
TELEGRAM_BOT_USERNAME = env("TELEGRAM_BOT_USERNAME", default="eatfit24_bot")
PERSONAL_PLAN_DAILY_LIMIT = env.int("PERSONAL_PLAN_DAILY_LIMIT", default=3)
```

---

## Сводная таблица

| Endpoint | Метод | Защита | Записывает в БД |
|----------|-------|--------|-----------------|
| `/save-test/` | POST | X-Bot-Secret | TelegramUser, Profile, DailyGoal |
| `/users/get-or-create/` | GET | X-Bot-Secret | TelegramUser, User |
| `/personal-plan/survey/` | POST | X-Bot-Secret | PersonalPlanSurvey |
| `/personal-plan/plan/` | POST | X-Bot-Secret | PersonalPlan |
| `/personal-plan/count-today/` | GET | X-Bot-Secret | — |
| `/invite-link/` | GET | — | — |
