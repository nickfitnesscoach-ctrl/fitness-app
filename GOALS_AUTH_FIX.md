# Быстрое руководство: Исправление авторизации для целей КБЖУ

## Проблема
Обычные пользователи получают **HTTP 500** при сохранении целей КБЖУ в WebApp.

## Причина
`DailyGoalSerializer` не имел метода `update()` и не проверял авторизацию → падал с ошибкой при попытке обновить цели для неаутентифицированного пользователя.

---

## Быстрое исправление (3 файла)

### 1. backend/apps/nutrition/serializers.py

**Найти** `DailyGoalSerializer` и **заменить** методы `create()` и добавить `update()`:

```python
class DailyGoalSerializer(serializers.ModelSerializer):
    # ... (Meta и validate_calories остаются без изменений)

    def create(self, validated_data):
        """Create daily goal for current user."""
        request = self.context.get('request')
        if not request or not request.user or not request.user.is_authenticated:
            raise serializers.ValidationError("User must be authenticated")

        validated_data['user'] = request.user

        # Деактивируем все предыдущие цели при создании новой активной
        if validated_data.get('is_active', True):
            DailyGoal.objects.filter(user=request.user, is_active=True).update(is_active=False)

        return super().create(validated_data)

    def update(self, instance, validated_data):
        """Update daily goal ensuring user ownership."""
        request = self.context.get('request')
        if not request or not request.user or not request.user.is_authenticated:
            raise serializers.ValidationError("User must be authenticated")

        # Verify ownership
        if instance.user != request.user:
            raise serializers.ValidationError("Cannot update goal of another user")

        # Если устанавливаем is_active=True, деактивируем другие цели
        if validated_data.get('is_active', False) and not instance.is_active:
            DailyGoal.objects.filter(
                user=request.user,
                is_active=True
            ).exclude(id=instance.id).update(is_active=False)

        return super().update(instance, validated_data)
```

**Строки:** [145-176](backend/apps/nutrition/serializers.py#L145-L176)

---

### 2. backend/apps/nutrition/views.py

**Найти** `DailyGoalView.put()` и **добавить** в начало метода:

```python
def put(self, request, *args, **kwargs):
    # Проверяем аутентификацию
    if not request.user or not request.user.is_authenticated:
        logger.warning("[DailyGoal] PUT called with unauthenticated user")
        logger.warning("[DailyGoal] Headers: X-Telegram-ID=%s, X-Telegram-Init-Data=%s",
                     request.META.get('HTTP_X_TELEGRAM_ID', 'NOT SET'),
                     'SET' if request.META.get('HTTP_X_TELEGRAM_INIT_DATA') else 'NOT SET')
        return Response(
            {"detail": "unauthenticated_webapp_user"},
            status=status.HTTP_401_UNAUTHORIZED
        )

    telegram_id = getattr(request.user, 'telegram_profile', None)
    logger.info("[DailyGoal] PUT called by user=%s telegram_id=%s data=%s",
               request.user.id,
               telegram_id.telegram_id if telegram_id else 'N/A',
               request.data)

    # ... (остальной код без изменений)
```

Аналогично для `DailyGoalView.patch()`:

```python
def patch(self, request, *args, **kwargs):
    # Проверяем аутентификацию
    if not request.user or not request.user.is_authenticated:
        logger.warning("[DailyGoal] PATCH called with unauthenticated user")
        return Response(
            {"detail": "unauthenticated_webapp_user"},
            status=status.HTTP_401_UNAUTHORIZED
        )

    logger.info("[DailyGoal] PATCH called by user=%s data=%s", request.user.id, request.data)

    # ... (остальной код без изменений)
```

**Строки:** [360-432](backend/apps/nutrition/views.py#L360-L432)

---

### 3. backend/apps/telegram/authentication.py

**Найти** `TelegramWebAppAuthentication.get_or_create_user()` и **добавить** после создания `TelegramUser`:

```python
# После строки: telegram_user = TelegramUser.objects.create(...)

# Гарантируем, что у каждого Telegram-пользователя есть профиль
try:
    Profile.objects.get_or_create(user=user)
except Exception as exc:
    logger.exception(
        "[TelegramWebAppAuth] Failed to ensure Profile for user %s: %s", user.pk, exc
    )
```

**Строки:** [125-131](backend/apps/telegram/authentication.py#L125-L131)

---

## Проверка

### 1. Перезапустить backend
```bash
# Если Docker
docker restart fm-backend

# Если локальная разработка
# Перезапустить python manage.py runserver
```

### 2. Тест
1. Открыть WebApp **обычным пользователем** (НЕ админом)
2. Перейти на страницу профиля
3. Задать цели КБЖУ:
   - Калории: 2000
   - Белки: 150
   - Жиры: 60
   - Углеводы: 200
4. Нажать "Сохранить"

**Ожидаемый результат:**
```
✅ HTTP 200 OK (или 201 Created)
{
  "id": 5,
  "calories": 2000,
  "protein": 150.0,
  "fat": 60.0,
  "carbohydrates": 200.0,
  "source": "MANUAL",
  "is_active": true
}
```

**Было ДО исправления:**
```
❌ HTTP 500 Internal Server Error
```

---

## Логи для проверки

### Успешное сохранение
```
INFO [TelegramHeaderAuth] Processing telegram_id=310151740, has_initData=True
INFO [TelegramHeaderAuth] Authenticated user_id=42 telegram_id=310151740
INFO [DailyGoal] PUT called by user=42 telegram_id=310151740 data={'calories': 2000, ...}
INFO [DailyGoal] Created new DailyGoal for user=42
```

### Ошибка авторизации (если headers отсутствуют)
```
WARNING [DailyGoal] PUT called with unauthenticated user
WARNING [DailyGoal] Headers: X-Telegram-ID=NOT SET, X-Telegram-Init-Data=NOT SET
```

**Response:**
```json
HTTP 401 Unauthorized
{"detail": "unauthenticated_webapp_user"}
```

---

## Что было исправлено

| Проблема | До | После |
|----------|-----|-------|
| **DailyGoalSerializer.update()** | ❌ Отсутствовал | ✅ Добавлен с проверкой авторизации |
| **DailyGoalSerializer.create()** | ❌ Не проверял авторизацию | ✅ Проверяет `request.user.is_authenticated` |
| **DailyGoalView.put()** | ❌ Возвращал 500 при отсутствии user | ✅ Возвращает 401 с понятным сообщением |
| **DailyGoalView.patch()** | ❌ Возвращал 500 при отсутствии user | ✅ Возвращает 401 с понятным сообщением |
| **Profile для новых пользователей** | ❌ Мог отсутствовать | ✅ Создаётся автоматически |
| **Логирование** | ❌ Минимальное | ✅ Подробное с user_id и telegram_id |

---

## Детальный отчёт

Смотри полный отчёт с архитектурой и сценариями тестирования:
- [WEBAPP_AUTH_FIX_REPORT.md](WEBAPP_AUTH_FIX_REPORT.md) - детальный анализ
- [ARCHITECTURE_AUDIT_REPORT.md](ARCHITECTURE_AUDIT_REPORT.md) - общий аудит

---

**Дата:** 2025-11-24
**Версия:** 1.0
**Исправлено файлов:** 3
**Время исправления:** 5 минут
