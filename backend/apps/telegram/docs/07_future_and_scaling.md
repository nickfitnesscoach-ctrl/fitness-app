# Масштабирование и развитие

| | |
|---|---|
| **Статус** | production-ready |
| **Владелец** | `apps/telegram/` |
| **Проверено** | 2024-12-16 |
| **Правило** | Меняешь код в `apps/telegram/*` → обнови docs |

---

## Текущее состояние

Telegram-домен рассчитан на:
- **~1,000-10,000** активных пользователей
- **~100** запросов/минуту к Bot API
- **~50** запросов/минуту к Trainer Panel
- **1** тренер/администратор

---

## Сценарий: 100,000 пользователей

### Узкие места

| Компонент | Проблема | Решение |
|-----------|----------|---------|
| **initData валидация** | CPU-bound (HMAC на каждый запрос) | Кеширование результата на время запроса уже есть |
| **TelegramUser lookup** | N запросов при показе списка | Уже используем `select_related`, `only()` |
| **Billing adapter** | N+1 при получении подписок | Уже используем batch `get_subscriptions_for_users()` |
| **Trainer Panel списки** | Медленная пагинация | Добавить cursor-based pagination |
| **PersonalPlan генерация** | AI bottleneck | Очереди, лимиты уже есть |

### Рекомендации

#### 1. Cursor-based pagination для больших списков

```python
# Вместо offset-based
GET /applications/?offset=10000&limit=100  # Медленно

# Cursor-based
GET /applications/?cursor=eyJpZCI6IDEyMzQ1fQ==&limit=100  # Быстро
```

#### 2. Кеширование метрик

```python
from django.core.cache import cache

def get_subscribers_metrics():
    cached = cache.get("trainer_panel:subscriber_metrics")
    if cached:
        return cached
    
    metrics = _calculate_metrics()  # Тяжёлый запрос
    cache.set("trainer_panel:subscriber_metrics", metrics, timeout=300)
    return metrics
```

#### 3. Read replicas для Trainer Panel

```python
# settings.py
DATABASES = {
    'default': {...},
    'replica': {...},
}

# views.py
def get_applications_api(request):
    qs = TelegramUser.objects.using('replica').filter(...)
```

---

## Сценарий: Несколько администраторов

### Текущее ограничение

`TELEGRAM_ADMINS` — простой список ID. Все админы имеют одинаковые права.

### Рекомендации

#### 1. Роли и разрешения

```python
# Расширить TelegramUser
class TelegramUser(models.Model):
    ...
    admin_role = models.CharField(
        max_length=20,
        choices=[
            ("owner", "Владелец"),
            ("trainer", "Тренер"),
            ("support", "Поддержка"),
        ],
        null=True,
        blank=True,
    )
```

#### 2. Гранулярные права

```python
ADMIN_ROLES = {
    "owner": ["view_applications", "manage_clients", "view_revenue", "manage_admins"],
    "trainer": ["view_applications", "manage_clients"],
    "support": ["view_applications"],
}
```

---

## Сценарий: Мульти-тенантность

Если нужно поддержать несколько тренеров с отдельными базами клиентов.

### Подход 1: Tenant field

```python
class TelegramUser(models.Model):
    ...
    tenant_id = models.IntegerField(db_index=True, null=True)
    
# Все запросы фильтруются по tenant
TelegramUser.objects.filter(tenant_id=request.tenant_id, ...)
```

### Подход 2: Отдельные базы данных

```python
DATABASE_ROUTERS = ['apps.telegram.routers.TenantRouter']
```

---

## Потенциальные улучшения

### 1. WebSocket для Trainer Panel

Вместо polling — real-time обновления при новых заявках.

```python
# consumers.py
class TrainerPanelConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        if not await self.is_admin():
            await self.close()
            return
        await self.channel_layer.group_add("trainer_panel", self.channel_name)
```

### 2. Аналитика и метрики

```python
# Prometheus metrics
from prometheus_client import Counter, Histogram

telegram_auth_counter = Counter('telegram_auth_total', 'Total auth attempts')
telegram_auth_latency = Histogram('telegram_auth_seconds', 'Auth latency')
```

### 3. Rate limiting по пользователям

```python
from django_ratelimit.decorators import ratelimit

@ratelimit(key='user_or_ip', rate='100/h', method='POST')
def save_test_results(request):
    ...
```

### 4. Асинхронная генерация планов

```python
# Celery task
@shared_task
def generate_personal_plan_async(telegram_id: int, survey_id: int):
    # AI генерация
    # Уведомление пользователя через бота
```

---

## Мониторинг

### Ключевые метрики

| Метрика | Алерт при |
|---------|-----------|
| `telegram_auth_errors` | > 10/min |
| `bot_api_403_responses` | > 5/min (неверный secret?) |
| `trainer_panel_latency_p99` | > 2s |
| `personal_plan_generation_time` | > 30s |
| `daily_active_users` | Падение > 20% |

### Логирование

```python
# Важные события для мониторинга
logger.info("telegram_auth_success", extra={"telegram_id": telegram_id})
logger.warning("bot_secret_mismatch", extra={"ip": request.META.get("REMOTE_ADDR")})
logger.error("billing_adapter_timeout", extra={"user_ids_count": len(user_ids)})
```

---

## Безопасность в масштабе

### 1. Ротация TELEGRAM_BOT_API_SECRET

```bash
# Генерация нового секрета
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Обновление
1. Добавить новый секрет в .env
2. Обновить бота
3. Удалить старый секрет
```

### 2. Audit log

```python
class AuditLog(models.Model):
    action = models.CharField(max_length=50)  # "add_client", "remove_client"
    actor_telegram_id = models.BigIntegerField()
    target_telegram_id = models.BigIntegerField(null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(null=True)
```

### 3. IP whitelist для Bot API

```python
# settings.py
BOT_API_ALLOWED_IPS = ["1.2.3.4", "5.6.7.8"]

# middleware or view
def _bot_secret_ok(request):
    ip = request.META.get("REMOTE_ADDR")
    if settings.BOT_API_ALLOWED_IPS and ip not in settings.BOT_API_ALLOWED_IPS:
        return False
    # ... остальная проверка
```

---

## Чек-лист перед масштабированием

- [ ] Добавить мониторинг ключевых метрик
- [ ] Настроить алерты на ошибки аутентификации
- [ ] Проверить индексы в БД (`EXPLAIN ANALYZE` на тяжёлых запросах)
- [ ] Настроить кеширование для read-heavy эндпоинтов
- [ ] Рассмотреть read replicas для Trainer Panel
- [ ] Добавить rate limiting на Bot API
- [ ] Настроить audit log для административных действий
