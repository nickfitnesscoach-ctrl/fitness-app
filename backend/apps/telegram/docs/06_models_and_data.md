# Модели и данные Telegram

| | |
|---|---|
| **Статус** | production-ready |
| **Владелец** | `apps/telegram/` |
| **Проверено** | 2024-12-16 |
| **Правило** | Меняешь код в `apps/telegram/*` → обнови docs |

---

## Обзор

Telegram-домен владеет тремя моделями:

| Модель | Назначение | Таблица |
|--------|------------|---------|
| `TelegramUser` | Профиль Telegram-пользователя | `telegram_telegramuser` |
| `PersonalPlanSurvey` | Анкета перед генерацией плана | `telegram_personalplansurvey` |
| `PersonalPlan` | Сгенерированный AI-план | `telegram_personalplan` |

---

## TelegramUser

### Назначение

Связывает Django User с данными из Telegram. Также хранит результаты AI-теста и рекомендации КБЖУ.

### Связи

```
┌─────────────────┐      ┌─────────────────┐
│   Django User   │◄────►│  TelegramUser   │
│                 │ 1:1  │                 │
│  • id           │      │  • user_id (FK) │
│  • username     │      │  • telegram_id  │
│  • first_name   │      │  • username     │
│  • last_name    │      │  • ...          │
└─────────────────┘      └─────────────────┘
        ▲                        ▲
        │                        │
        │ 1:1              related_name
        │                  "telegram_profile"
        ▼
┌─────────────────┐
│     Profile     │
│  (apps/users/)  │
└─────────────────┘
```

### Поля

| Поле | Тип | Критичность | Описание |
|------|-----|-------------|----------|
| `id` | AutoField | 🔒 | Внутренний ID |
| `user` | OneToOneField | 🔒 | Связь с Django User |
| `telegram_id` | BigIntegerField | 🔒 | **UNIQUE**, Telegram ID пользователя |
| `username` | CharField | ✏️ | @username (может быть null) |
| `first_name` | CharField | ✏️ | Имя из Telegram |
| `last_name` | CharField | ✏️ | Фамилия из Telegram |
| `language_code` | CharField | ✏️ | Код языка (ru, en, etc.) |
| `is_premium` | BooleanField | ✏️ | Telegram Premium статус |
| `ai_test_completed` | BooleanField | ⚠️ | Прошёл ли AI-тест |
| `ai_test_answers` | JSONField | ⚠️ | Ответы из AI-теста |
| `is_client` | BooleanField | ⚠️ | Добавлен ли в клиенты |
| `recommended_calories` | IntegerField | ✏️ | Рекомендация калорий |
| `recommended_protein` | DecimalField | ✏️ | Рекомендация белков (г) |
| `recommended_fat` | DecimalField | ✏️ | Рекомендация жиров (г) |
| `recommended_carbs` | DecimalField | ✏️ | Рекомендация углеводов (г) |
| `created_at` | DateTimeField | 🔒 | Дата создания |
| `updated_at` | DateTimeField | 🔒 | Дата обновления |

### Легенда критичности

| Символ | Значение |
|--------|----------|
| 🔒 | Нельзя менять вручную (генерируется автоматически) |
| ⚠️ | Можно менять, но с осторожностью (влияет на бизнес-логику) |
| ✏️ | Можно менять свободно |

### Индексы

```python
indexes = [
    models.Index(fields=["telegram_id"]),
    models.Index(fields=["ai_test_completed"]),
    models.Index(fields=["is_client"]),
]
```

### Откуда приходят данные

| Поле | Источник |
|------|----------|
| `telegram_id`, `username`, `first_name`, `last_name`, `language_code`, `is_premium` | Telegram (initData или Bot API) |
| `ai_test_completed`, `ai_test_answers` | Telegram Bot (через `/save-test/`) |
| `is_client` | Trainer Panel (вручную) |
| `recommended_*` | Расчёт DailyGoal после теста |

### Валидация

```python
def clean(self):
    if self.telegram_id is not None and self.telegram_id <= 0:
        raise ValidationError({"telegram_id": "Должен быть положительным"})
    
    if self.ai_test_answers is not None and not isinstance(self.ai_test_answers, dict):
        raise ValidationError({"ai_test_answers": "Должен быть объектом"})
```

---

## PersonalPlanSurvey

### Назначение

Анкета, которую заполняет пользователь перед генерацией персонального плана. Содержит все данные для AI.

### Связи

```
┌─────────────────┐      ┌───────────────────────┐
│   Django User   │◄────►│  PersonalPlanSurvey   │
│                 │ 1:N  │                       │
│                 │      │  • user_id (FK)       │
│                 │      │  • gender, age, ...   │
└─────────────────┘      └───────────────────────┘
                                    │
                                    │ 1:N
                                    ▼
                         ┌─────────────────┐
                         │  PersonalPlan   │
                         │                 │
                         │  • survey_id    │
                         └─────────────────┘
```

### Поля

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | AutoField | Внутренний ID |
| `user` | ForeignKey | Связь с Django User |
| `gender` | CharField | "male" или "female" |
| `age` | PositiveSmallIntegerField | Возраст (14-80) |
| `height_cm` | PositiveSmallIntegerField | Рост в см (120-250) |
| `weight_kg` | DecimalField | Текущий вес |
| `target_weight_kg` | DecimalField | Целевой вес (опционально) |
| `activity` | CharField | Уровень активности |
| `training_level` | CharField | Уровень тренированности |
| `body_goals` | JSONField | Цели (список строк) |
| `health_limitations` | JSONField | Ограничения (список строк) |
| `body_now_id` | PositiveSmallIntegerField | ID типа фигуры сейчас |
| `body_now_label` | TextField | Описание типа фигуры сейчас |
| `body_now_file` | TextField | Файл картинки |
| `body_ideal_id` | PositiveSmallIntegerField | ID желаемого типа фигуры |
| `body_ideal_label` | TextField | Описание желаемого типа |
| `body_ideal_file` | TextField | Файл картинки |
| `timezone` | CharField | Часовой пояс (например, "Europe/Moscow") |
| `utc_offset_minutes` | IntegerField | Смещение UTC в минутах |
| `completed_at` | DateTimeField | Когда завершена анкета |
| `created_at` | DateTimeField | Дата создания |
| `updated_at` | DateTimeField | Дата обновления |

### Choices

**activity:**
```python
ACTIVITY_CHOICES = [
    ("sedentary", "Сидячий образ жизни"),
    ("light", "Легкая активность"),
    ("moderate", "Умеренная активность"),
    ("active", "Активный образ жизни"),
    ("very_active", "Очень активный образ жизни"),
]
```

### Индексы

```python
indexes = [
    models.Index(fields=["user", "completed_at"]),
    models.Index(fields=["created_at"]),
]
```

### Валидация

```python
def clean(self):
    if not (14 <= self.age <= 80):
        raise ValidationError({"age": "Возраст 14-80"})
    if not (120 <= self.height_cm <= 250):
        raise ValidationError({"height_cm": "Рост 120-250"})
    if not (-840 <= self.utc_offset_minutes <= 840):
        raise ValidationError({"utc_offset_minutes": "Смещение -840..840"})
```

---

## PersonalPlan

### Назначение

Сгенерированный AI план питания/тренировок. Привязан к пользователю и опционально к анкете.

### Связи

```
┌─────────────────┐
│   Django User   │
└─────────────────┘
        │
        │ 1:N
        ▼
┌─────────────────┐      ┌───────────────────────┐
│  PersonalPlan   │─────►│  PersonalPlanSurvey   │
│                 │ N:1  │                       │
│  • user_id      │      │  (опционально)        │
│  • survey_id    │      │                       │
│  • ai_text      │      │                       │
└─────────────────┘      └───────────────────────┘
```

### Поля

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | AutoField | Внутренний ID |
| `user` | ForeignKey | Связь с Django User |
| `survey` | ForeignKey | Связь с анкетой (опционально, SET_NULL) |
| `ai_text` | TextField | Текст плана от AI |
| `ai_model` | CharField | Модель AI (gpt-4, claude, etc.) |
| `prompt_version` | CharField | Версия промпта (для аудита) |
| `created_at` | DateTimeField | Дата создания |

### Индексы

```python
indexes = [
    models.Index(fields=["user", "created_at"]),
    models.Index(fields=["survey"]),
]
```

---

## Важные ограничения

### Что нельзя менять без миграции

> [!CAUTION]
> Изменение этих полей требует Django миграции и возможно data migration.

| Поле | Причина |
|------|---------|
| `TelegramUser.telegram_id` | UNIQUE constraint, db_index |
| `TelegramUser.user` | OneToOneField, связь с auth.User |
| `PersonalPlanSurvey.user` | ForeignKey, каскадное удаление |
| `PersonalPlan.user` | ForeignKey, каскадное удаление |

### Что можно менять свободно

| Поле | Примечание |
|------|------------|
| `TelegramUser.username`, `first_name`, `last_name` | Обновляются при каждом логине |
| `TelegramUser.is_premium`, `language_code` | Информационные поля |
| `TelegramUser.recommended_*` | Пересчитываются автоматически |
| `PersonalPlan.ai_text` | Но зачем? |

### ai_test_answers структура

```json
{
  "gender": "male",
  "age": 30,
  "weight": 80,
  "height": 175,
  "goal": "weight_loss",
  "activity_level": "medium",
  "target_weight": 70,
  "training_level": "beginner",
  "goals": ["lose_fat", "build_muscle"],
  "health_restrictions": ["back_pain"],
  "current_body_type": "endomorph",
  "ideal_body_type": "mesomorph",
  "timezone": "Europe/Moscow"
}
```

> [!NOTE]
> Структура может расширяться. Код должен обрабатывать отсутствие полей gracefully.

---

## Связь с другими моделями

### С apps/users/

```python
# Получить TelegramUser из User
user.telegram_profile  # related_name

# Получить Profile для пользователя
user.profile
```

### С apps/nutrition/

```python
# Получить DailyGoal для пользователя
DailyGoal.objects.filter(user=user, is_active=True).first()
```

### С apps/billing/

```python
# Получить Subscription для пользователя  
user.subscription  # OneToOne relation

# НО! В trainer_panel используйте billing_adapter
from apps.telegram.trainer_panel.billing_adapter import get_user_subscription_info
info = get_user_subscription_info(user)
```

---

## Примеры запросов

### Все пользователи прошедшие тест

```python
TelegramUser.objects.filter(ai_test_completed=True)
```

### Клиенты с подпиской

```python
from apps.telegram.trainer_panel.billing_adapter import get_subscriptions_for_users

clients = TelegramUser.objects.filter(is_client=True).select_related("user")
user_ids = [c.user_id for c in clients]
subscriptions = get_subscriptions_for_users(user_ids)

for client in clients:
    sub = subscriptions.get(client.user_id)
    print(f"{client.display_name}: {sub['plan_type']}")
```

### Найти TelegramUser по telegram_id

```python
TelegramUser.objects.filter(telegram_id=123456789).first()
```

### Последний план пользователя

```python
PersonalPlan.objects.filter(user=user).order_by("-created_at").first()
```

---

## Миграции

> [!WARNING]
> Перед изменением моделей создайте backup базы данных.

### Создание миграции

```bash
python manage.py makemigrations telegram
```

### Применение миграции

```bash
python manage.py migrate telegram
```

### Data migration пример

Если нужно мигрировать данные (например, переименовать поле):

```python
# telegram/migrations/00XX_migrate_field.py

from django.db import migrations

def migrate_data(apps, schema_editor):
    TelegramUser = apps.get_model('telegram', 'TelegramUser')
    for user in TelegramUser.objects.all():
        user.new_field = user.old_field
        user.save(update_fields=['new_field'])

class Migration(migrations.Migration):
    dependencies = [
        ('telegram', '00XX_add_new_field'),
    ]
    
    operations = [
        migrations.RunPython(migrate_data),
    ]
```
