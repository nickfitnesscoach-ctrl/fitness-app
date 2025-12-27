# Celery Beat — Планировщик Задач

## Что это такое

**Celery Beat** — это "будильник" для EatFit24.

Он запускает регулярные задачи по расписанию:
- Автопродление подписок (каждый час)
- Проверка застрявших платежей (каждые 5 минут)
- Очистка устаревших данных (каждый час)

**Аналогия:** cron, но для Python-приложений.

---

## Где задаётся расписание

Файл:
```
backend/config/celery.py
```

Пример:
```python
beat_schedule = {
    'billing-process-due-renewals': {
        'task': 'apps.billing.tasks_recurring.process_due_renewals',
        'schedule': crontab(minute=0, hour='*/1'),  # Каждый час
    },
}
```

**Важно:** Код — единственный источник правды. Если хочешь изменить расписание — меняй код.

---

## Где Beat хранит свои данные

**Путь внутри контейнера:**
```
/app/celerybeat-data/celerybeat-schedule
```

**Что это:**
- Runtime-файл (создаётся автоматически при запуске)
- Хранит информацию о том, когда последний раз задачи запускались
- **Не хранится в git** (это не код, это рабочие данные)
- Живёт в Docker volume (см. ниже)

---

## Что такое Docker Volume (коротко)

```
Контейнер = временный (удалили — исчез)
Volume    = постоянный (переживает удаление контейнера)
```

**Для чего это нужно:**
- Контейнер `celery-beat` можно пересоздать
- Файл `celerybeat-schedule` останется в volume
- Beat продолжит работу с того места, где остановился

**Схема:**
```
┌─────────────────────┐
│ celery-beat         │
│ контейнер (временно)│
└──────────┬──────────┘
           │
           ▼
┌──────────────────────────────┐
│ eatfit24-celerybeat-data     │
│ volume (постоянно)           │
│                              │
│ celerybeat-schedule ◄────────┤ Beat пишет сюда
└──────────────────────────────┘
```

---

## Как проверить, что всё работает

### 1. Контейнер запущен
```bash
docker ps | grep celery-beat
```

Ожидается:
```
eatfit24-celery-beat   Up X minutes
```

### 2. Задачи отправляются
```bash
docker logs eatfit24-celery-beat | grep "Sending due task"
```

Ожидается (примеры):
```
Scheduler: Sending due task billing-retry-stuck-webhooks
Scheduler: Sending due task billing-process-due-renewals
```

### 3. Файл schedule существует
```bash
docker exec eatfit24-celery-beat ls -la /app/celerybeat-data
```

Ожидается:
```
-rw-r--r-- 1 appuser appuser 16384 Dec 27 13:27 celerybeat-schedule
```

---

## Главное правило

### Изменил расписание в `celery.py` → пересоздай контейнер

**Команды:**
```bash
cd /opt/EatFit24
docker compose rm -f celery-beat
docker compose up -d celery-beat
```

**Почему:**
- Beat читает расписание из кода **только при старте**
- Просто перезапуск (`restart`) не помогает — нужно пересоздание

---

## Что делать, если задачи ведут себя странно

**Симптомы:**
- Задачи не запускаются по расписанию
- Логи молчат (нет "Sending due task")
- Контейнер перезапускается

**Решение:**
```bash
cd /opt/EatFit24

# Остановить и удалить контейнер
docker compose rm -f celery-beat

# Создать заново (пересоберёт образ, если нужно)
docker compose up -d celery-beat

# Проверить логи
docker logs -f eatfit24-celery-beat
```

**Ожидаемый вывод в логах:**
```
celery beat v5.6.0 (recovery) is starting.
...
db -> /app/celerybeat-data/celerybeat-schedule
beat: Starting...
```

Если видишь `Permission denied` или `No such file or directory` — значит volume отмонтировался. Свяжись с DevOps.

---

## Краткая справка

| Вопрос | Ответ |
|--------|-------|
| Где код расписания? | `backend/config/celery.py` |
| Где runtime-данные? | `/app/celerybeat-data/celerybeat-schedule` |
| Изменил код — что делать? | `docker compose rm -f celery-beat && docker compose up -d celery-beat` |
| Проверить работу | `docker logs eatfit24-celery-beat \| grep "Sending due task"` |
| Контейнер падает | Пересоздать контейнер (команды выше) |

---

**Документация актуальна на:** 2025-12-27  
**Автор:** DevOps Agent (Claude Sonnet 4.5)
