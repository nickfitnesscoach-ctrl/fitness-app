# Лимиты и использование

## Обзор

Система лимитов контролирует количество AI-анализов фото в день.

---

## Лимиты по планам

| План | Лимит фото/день | История |
|------|-----------------|---------|
| `FREE` | 3 | 7 дней |
| `PRO_MONTHLY` | ∞ (null) | ∞ |
| `PRO_YEARLY` | ∞ (null) | ∞ |

---

## Модуль usage.py

### DailyUsage

Хранит использование по дням:

```python
class DailyUsage(models.Model):
    user = ForeignKey(User)
    date = DateField()
    photo_analyses = IntegerField(default=0)
```

### Ключевые функции

```python
# Получить использование за сегодня
get_today_usage(user) -> int

# Инкрементировать использование
increment_usage(user) -> int

# Проверить, можно ли ещё
can_analyze_photo(user) -> bool

# Оставшиеся анализы
remaining_analyses(user) -> int | None  # None = безлимит
```

---

## Атомарность

Защита от race condition:

```python
@transaction.atomic
def increment_usage(user):
    usage, _ = DailyUsage.objects.select_for_update().get_or_create(
        user=user,
        date=date.today(),
    )
    usage.photo_analyses = F('photo_analyses') + 1
    usage.save()
```

---

## API Response

### GET /billing/me/

```json
{
  "plan_code": "FREE",
  "plan_name": "Бесплатный",
  "is_active": true,
  "end_date": null,
  "daily_photo_limit": 3,
  "used_today": 2,
  "remaining_today": 1
}
```

Для PRO:

```json
{
  "plan_code": "PRO_MONTHLY",
  "plan_name": "PRO месячный",
  "is_active": true,
  "end_date": "2025-01-18",
  "daily_photo_limit": null,
  "used_today": 15,
  "remaining_today": null
}
```

---

## Проверка в коде

### AI модуль

```python
from apps.billing.usage import can_analyze_photo, increment_usage

def analyze_food_photo(user, photo):
    if not can_analyze_photo(user):
        raise LimitExceededError("Daily limit reached")
    
    result = ai_service.analyze(photo)
    increment_usage(user)
    return result
```

---

## Кеширование

Для оптимизации КБЖУ-лимитов используется кеш плана:

```python
CACHE_KEY = f"user_plan:{user_id}"
CACHE_TTL = 300  # 5 минут

def get_user_plan_cached(user_id):
    cached = cache.get(CACHE_KEY)
    if cached:
        return cached
    plan = Subscription.objects.get(user_id=user_id).plan
    cache.set(CACHE_KEY, plan, CACHE_TTL)
    return plan

def invalidate_user_plan_cache(user_id):
    cache.delete(CACHE_KEY)
```

Инвалидация происходит при:
- Успешном webhook (`handlers.py`)
- Изменении подписки через admin

---

## Сброс лимитов

Лимиты сбрасываются автоматически каждый день (по дате `DailyUsage.date`).

Часовой пояс: берётся из `Profile.timezone` или `settings.TIME_ZONE`.
