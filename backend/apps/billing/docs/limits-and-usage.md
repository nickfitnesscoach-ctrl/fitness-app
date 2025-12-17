# Лимиты и использование

## Обзор

Система лимитов контролирует использование AI-функций в зависимости от плана подписки.

## Модель DailyUsage

```python
class DailyUsage(models.Model):
    user = models.ForeignKey(User, ...)
    date = models.DateField(default=today)
    photo_ai_requests = models.PositiveIntegerField(default=0)
```

Уникальность: `(user, date)` — одна запись на пользователя в день.

## Лимиты по планам

| План | `daily_photo_limit` | Поведение |
|------|---------------------|-----------|
| FREE | 3 | Максимум 3 фото в день |
| PRO_MONTHLY | `null` | Безлимит |
| PRO_YEARLY | `null` | Безлимит |

`null` = безлимит.

## Проверка лимита

### Атомарная проверка + инкремент

```python
allowed, current_count = DailyUsage.objects.check_and_increment_if_allowed(
    user=user,
    limit=plan.daily_photo_limit,
    amount=1
)

if not allowed:
    return Response({"error": "daily_limit_reached"}, status=429)
```

**Важно:** Проверка и инкремент происходят **атомарно** в одной транзакции с блокировкой строки.

### Почему атомарно?

Race condition без атомарности:
```
Request 1: check (count=2, limit=3) → OK
Request 2: check (count=2, limit=3) → OK
Request 1: increment (count=3)
Request 2: increment (count=4)  # Превышение!
```

С атомарностью:
```
Request 1: lock + check + increment (count=3) → OK
Request 2: wait... lock + check (count=3, limit=3) → REJECT
```

## API

### Получение статуса

```
GET /api/v1/billing/me/
```

```json
{
  "plan_code": "FREE",
  "daily_photo_limit": 3,
  "used_today": 2,
  "remaining_today": 1
}
```

### Проверка перед операцией

```python
# В views/services где нужна проверка лимита
from apps.billing.usage import DailyUsage

def some_ai_operation(request):
    subscription = request.user.subscription
    limit = subscription.plan.daily_photo_limit
    
    allowed, count = DailyUsage.objects.check_and_increment_if_allowed(
        user=request.user,
        limit=limit,
        amount=1
    )
    
    if not allowed:
        return Response({
            "error": "DAILY_LIMIT_REACHED",
            "limit": limit,
            "used": count
        }, status=429)
    
    # Продолжаем операцию...
```

## Методы DailyUsageManager

### get_today(user)

Получает или создаёт запись на сегодня.

```python
usage = DailyUsage.objects.get_today(user)
print(usage.photo_ai_requests)  # 5
```

### increment_photo_ai_requests(user, amount=1)

Увеличивает счётчик атомарно (без проверки лимита).

```python
usage = DailyUsage.objects.increment_photo_ai_requests(user, amount=1)
```

### check_and_increment_if_allowed(user, limit, amount=1)

Атомарная проверка + инкремент.

```python
allowed, count = DailyUsage.objects.check_and_increment_if_allowed(
    user=user,
    limit=3,  # None = безлимит
    amount=1
)
```

### reset_today(user)

Обнуляет счётчик (для тестов/админки).

```python
DailyUsage.objects.reset_today(user)
```

## Кеширование лимитов

Эффективный план кешируется:
```python
cache_key = f"user_plan:{user.id}"
```

Инвалидация происходит при:
- Изменении подписки
- Продлении подписки
- Смене плана

## Связь с биллингом

```
SubscriptionPlan.daily_photo_limit
        ↓
Subscription.plan
        ↓
DailyUsage.check_and_increment_if_allowed(limit=plan.daily_photo_limit)
```

## Troubleshooting

### Лимит "съехал"

1. Проверь `DailyUsage` для пользователя на сегодня
2. Проверь `Subscription.plan.daily_photo_limit`
3. Проверь кеш плана

### Всегда "лимит достигнут"

1. Проверь, не `0` ли `daily_photo_limit` (вместо `null`)
2. Проверь дату в `DailyUsage` — может быть не сегодня
