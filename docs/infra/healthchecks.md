# Health Checks в EatFit24

> **Путь:** Backend → `apps/common/views.py`  
> **Используется в:** Docker healthcheck, CI/CD деплой, мониторинг

---

## Endpoints

| Endpoint | Назначение | HTTP-код успеха | HTTP-код ошибки |
|----------|------------|-----------------|-----------------|
| `/health/` | Полная проверка | 200 | 500 |
| `/api/v1/health/` | Алиас `/health/` | 200 | 500 |
| `/ready/` | Readiness probe | 200 | 503 |
| `/live/` | Liveness probe | 200 | — |

---

## `/health/` — полная проверка здоровья

**Что проверяет:**

1. **Database (PostgreSQL)**
   - Выполняет `SELECT 1`
   - Если БД недоступна → возвращает 500

2. **Redis**
   - Записывает тестовый ключ `health_check_test`
   - Читает его обратно и проверяет значение
   - Если Redis недоступен или значение не совпадает → 500

**Пример успешного ответа:**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "python_version": "3.12.0",
  "database": "ok",
  "redis": "ok"
}
```

**Пример ошибки:**
```json
{
  "status": "error",
  "version": "1.0.0",
  "python_version": "3.12.0",
  "database": "ok",
  "redis": "error: Connection refused"
}
```

**Где используется:**
- Docker Compose healthcheck для `backend`
- CI/CD деплой — после `docker compose up` проверяет, что backend жив
- Host-level Nginx может использовать для upstream health

---

## `/ready/` — готовность принимать трафик

**Что проверяет:** то же самое, что `/health/`, но с другой семантикой:
- `/health/` — "сервис жив или мёртв"
- `/ready/` — "сервис готов принимать запросы"

**HTTP-коды:**
- `200` — ready, можно слать трафик
- `503 Service Unavailable` — not ready, не слать трафик

**Пример not_ready:**
```json
{
  "status": "not_ready",
  "checks": {
    "database": "not_ready: connection refused",
    "redis": "ready"
  }
}
```

**Где используется:**
- Kubernetes readiness probe (если мигрируете)
- Load balancer для вывода из rotation при проблемах

---

## `/live/` — liveness probe

**Что проверяет:** ничего, просто отвечает 200.

```json
{"status": "alive"}
```

**Смысл:** если Django process повис или упал — endpoint не ответит. Достаточно для определения, что процесс жив.

**Где используется:**
- Kubernetes liveness probe
- Watchdog-системы

---

## Использование в Docker Compose

```yaml
backend:
  healthcheck:
    test: ["CMD", "curl", "-f", "-H", "Host: eatfit24.ru", "http://localhost:8000/health/"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 30s
```

**Почему `Host: eatfit24.ru`:**  
Django проверяет `ALLOWED_HOSTS`. Без заголовка запрос будет отклонён с ошибкой `Invalid HTTP_HOST`.

---

## Почему деплой может упасть

### Причины падения health check после деплоя

| Симптом | Вероятная причина | Как диагностировать |
|---------|-------------------|---------------------|
| `database: error` | БД не успела подняться | `docker logs eatfit24-db` |
| `database: error` | Неверные креды в `.env` | Проверить `POSTGRES_*` переменные |
| `redis: error` | Redis не запустился | `docker logs eatfit24-redis` |
| `Connection refused` | Сервис не успел запуститься | Увеличить `start_period` |
| Timeout без ответа | OOM-kill контейнера | `docker stats`, проверить лимиты памяти |
| `Invalid HTTP_HOST` | Неверный Host заголовок | Исправить healthcheck команду |

### Типичные сценарии

**1. Миграции зависли**
```
Backend ждёт миграции → timeout → healthcheck fail → контейнер перезапускается → миграции снова → loop
```
**Решение:** увеличить `start_period` или чинить миграции.

**2. Redis OOM**
```
Celery накопил много задач → Redis съел память → OOM → backend не может подключиться
```
**Решение:** увеличить лимит памяти Redis или почистить очередь.

**3. Секреты не обновлены**
```
Код ожидает новый ENV → .env на сервере старый → ошибка при старте
```
**Решение:** обновить `.env` на сервере перед деплоем.

---

## Чеклист при падении деплоя

```bash
# 1. Статус контейнеров
docker compose ps

# 2. Логи проблемного сервиса
docker logs eatfit24-backend --tail 100

# 3. Ручная проверка health
curl -v -H "Host: eatfit24.ru" http://127.0.0.1:8000/health/

# 4. Проверка БД напрямую
docker exec -it eatfit24-db psql -U eatfit24 -d eatfit24 -c "SELECT 1"

# 5. Проверка Redis
docker exec -it eatfit24-redis redis-cli ping

# 6. Использование ресурсов
docker stats --no-stream
```

---

## Добавление нового health check

Если нужно добавить проверку нового сервиса (например, AI Proxy):

```python
# apps/common/views.py

# В health_check():
try:
    response = requests.get(settings.AI_PROXY_URL + '/health', timeout=5)
    if response.status_code == 200:
        health_status['ai_proxy'] = 'ok'
    else:
        raise Exception(f'Status {response.status_code}')
except Exception as e:
    health_status['status'] = 'error'
    health_status['ai_proxy'] = f'error: {str(e)}'
    return Response(health_status, status=500)
```

> **Важно:** не добавляй проверки сервисов, которые могут быть временно недоступны (внешние API). Это сделает основной сервис "нездоровым" из-за внешних причин.
