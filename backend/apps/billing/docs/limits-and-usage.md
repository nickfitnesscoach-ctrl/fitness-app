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
    date = DateField(default=_get_today)  # использует timezone.localdate()
    photo_ai_requests = PositiveIntegerField(default=0)
```

### Ключевые методы DailyUsageManager

```python
from apps.billing.usage import DailyUsage

# Получить использование за сегодня (создаёт запись если нет)
usage = DailyUsage.objects.get_today(user)
current_count = usage.photo_ai_requests

# Инкрементировать использование после успешного AI
usage = DailyUsage.objects.increment_photo_ai_requests(user)

# Атомарная проверка лимита + инкремент (для P1-4)
allowed, count = DailyUsage.objects.check_and_increment_if_allowed(
    user=user,
    limit=3,  # или None для безлимита
    amount=1
)
if not allowed:
    raise LimitExceededError("Daily limit reached")
```

### Функция _get_today() (P0-3 fix)

```python
def _get_today():
    """Единственный источник истины для 'сегодня' в usage модуле."""
    return timezone.localdate()
```

Все методы используют `_get_today()` для определения "сегодня", что гарантирует консистентность timezone.

---

## Атомарность (race condition protection)

Защита от race condition через `select_for_update`:

```python
# check_and_increment_if_allowed гарантирует атомарность:
# - блокирует строку для параллельных запросов
# - проверяет лимит ВНУТРИ транзакции
# - инкрементирует только если лимит не достигнут

with transaction.atomic():
    usage, _ = self.select_for_update().get_or_create(
        user=user,
        date=_get_today(),
        defaults={"photo_ai_requests": 0},
    )
    
    if usage.photo_ai_requests >= limit:
        return (False, usage.photo_ai_requests)  # Отказ
    
    self.filter(pk=usage.pk).update(
        photo_ai_requests=F("photo_ai_requests") + 1
    )
    return (True, usage.photo_ai_requests + 1)  # Успех
```

---

## API Response

### GET /api/v1/billing/me/

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

## Использование в AI модуле

### Celery task (tasks.py)

После успешного распознавания и сохранения items:

```python
# После transaction.atomic() в recognize_food_async:
if user_id:
    from apps.billing.usage import DailyUsage
    user = User.objects.get(id=user_id)
    DailyUsage.objects.increment_photo_ai_requests(user)
```

### View (P1-4: проверка ДО создания Meal)

```python
# В AIRecognitionView.post() перед созданием Meal:
from apps.billing.usage import DailyUsage
from apps.billing.services import get_effective_plan_for_user

plan = get_effective_plan_for_user(request.user)
allowed, count = DailyUsage.objects.check_and_increment_if_allowed(
    user=request.user,
    limit=plan.daily_photo_limit,  # None = безлимит
)

if not allowed:
    return Response(
        {"error": "Daily photo limit exceeded", "used": count},
        status=429
    )

# Только если allowed → создаём Meal
```

---

## Кеширование

Для оптимизации используется кеш плана:

```python
# apps/billing/services.py

CACHE_KEY = f"user_plan:{user_id}"
CACHE_TTL = 300  # 5 минут

def get_effective_plan_for_user(user) -> SubscriptionPlan:
    cache_key = f"user_plan:{user.id}"
    cached_plan_id = cache.get(cache_key)
    
    if cached_plan_id:
        return SubscriptionPlan.objects.get(id=cached_plan_id)
    
    plan = _get_effective_plan_uncached(user)
    cache.set(cache_key, plan.id, timeout=300)
    return plan

def invalidate_user_plan_cache(user_id):
    cache.delete(f"user_plan:{user_id}")
```

Инвалидация происходит при:
- Успешном webhook (`webhooks/handlers.py`)
- Изменении подписки через admin

---

## Сброс лимитов

Лимиты сбрасываются автоматически каждый день.

**Timezone policy:** используется `timezone.localdate()` — дата в часовом поясе пользователя/сервера.

---

## 🚫 Правило инкремента (INV-7)

> ⚠️ `increment_photo_ai_requests()` вызывается **ТОЛЬКО** после успешного ответа AI и сохранения результата.

```python
# ✅ ПРАВИЛЬНО (в Celery task)
result = service.recognize_food(...)
save_items_to_db(result.items)
DailyUsage.objects.increment_photo_ai_requests(user)
return result

# ❌ НЕПРАВИЛЬНО — инкремент до результата
DailyUsage.objects.increment_photo_ai_requests(user)
result = service.recognize_food(...)  # может упасть!
```

---

## Edge Cases

| Сценарий | Что происходит | Лимит списан? |
|----------|----------------|---------------|
| AI ответил ошибкой | Возвращаем ошибку пользователю | ❌ Нет |
| Celery worker упал | Task retry, повторный анализ | ❌ Нет (до успеха) |
| Timeout при анализе | Возвращаем ошибку | ❌ Нет |
| Успешный анализ | Результат сохранён | ✅ Да |
| Лимит исчерпан до запроса | 429 ДО создания Meal | ❌ Нет |
| Дублирующий запрос | Идемпотентность через meal_id | ✅ Один раз |

---

## Changelog

- **2025-12-24**: P1-1 — обновлена документация под фактический API
- **2025-12-24**: P0-3 — унифицирован timezone на `_get_today()` / `timezone.localdate()`
- **2025-12-24**: P0-1 — добавлен инкремент usage после успеха AI в tasks.py
