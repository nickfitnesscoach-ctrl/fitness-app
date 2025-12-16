# Telegram Operations Runbook

| | |
|---|---|
| **Статус** | production-ready |
| **SSOT** | Инциденты и восстановление |
| **Обновлено** | 2024-12-16 |

---

## Incident Response

### Scenario: Bot Token Leaked

**Симптомы:**
- Неавторизованные действия от имени бота
- Пользователи жалуются на странные сообщения
- initData от других ботов принимаются

**Действия:**

```bash
# 1. НЕМЕДЛЕННО revoke через @BotFather
# /mybots → [Bot] → API Token → Revoke

# 2. Получить новый токен от @BotFather

# 3. Обновить на сервере
ssh prod
nano .env  # TELEGRAM_BOT_TOKEN=<NEW_TOKEN>

# 4. Restart
docker-compose restart backend

# 5. Verify
curl -X POST https://<DOMAIN>/api/v1/telegram/auth/ \
  -H "Content-Type: application/json" \
  -H "X-Telegram-Init-Data: <VALID_INIT_DATA>"
# Expected: 200 с новым токеном
```

**После фикса:**
- [ ] Новый токен работает
- [ ] Старые initData → 401
- [ ] Логи чистые от токенов

---

### Scenario: Bot API Secret Leaked

**Симптомы:**
- Неавторизованные записи в БД
- Подозрительные данные в Trainer Panel

**Действия:**

```bash
# 1. Сгенерировать новый секрет
python -c "import secrets; print(secrets.token_urlsafe(32))"

# 2. Обновить .env
TELEGRAM_BOT_API_SECRET=<NEW_SECRET>

# 3. Обновить в боте (config бота)

# 4. Restart backend
docker-compose restart backend

# 5. Verify — без секрета должно быть 403
curl -X POST https://<DOMAIN>/api/v1/telegram/save-test/ \
  -H "Content-Type: application/json" \
  -d '{"telegram_id": 123}'
# Expected: 403
```

---

### Scenario: All Admins Locked Out (403)

**Симптомы:**
- Все админы получают 403 на Trainer Panel

**Диагностика:**

```bash
docker exec -it backend python manage.py shell -c \
  "from django.conf import settings; print(repr(settings.TELEGRAM_ADMINS))"
```

**Действия:**

```bash
# Если пусто или неверный формат
nano .env
# TELEGRAM_ADMINS=<ADMIN_TELEGRAM_ID>

docker-compose restart backend

# Verify
curl -X GET https://<DOMAIN>/api/v1/telegram/applications/ \
  -H "X-Telegram-Init-Data: <ADMIN_INIT_DATA>"
# Expected: 200
```

---

### Scenario: CI Fails on URL Import

**Симптомы:**
- CI падает на `from apps.telegram.urls import urlpatterns`

**Локальная диагностика:**

```bash
python -c "from apps.telegram.urls import urlpatterns; print(len(urlpatterns))"

# Если ошибка — проверить синтаксис
python -m py_compile apps/telegram/bot/views.py
python -m py_compile apps/telegram/auth/views.py
python -m py_compile apps/telegram/trainer_panel/views.py
```

**Частые причины:**
- Circular import → вынести в utils.py
- Missing view → проверить urls.py
- Syntax error → py_compile покажет

---

## Debug Mode Emergency

> [!CAUTION]
> Debug Mode в production = критическая уязвимость

**Проверка:**

```bash
docker exec -it backend python manage.py shell -c \
  "from django.conf import settings; print('DEBUG:', settings.DEBUG); print('WEBAPP_DEBUG:', getattr(settings, 'WEBAPP_DEBUG_MODE_ENABLED', False))"
```

**Ожидаемый результат:**
```
DEBUG: False
WEBAPP_DEBUG: False
```

**Если True → немедленно:**
```bash
# Обновить .env
DEBUG=False
WEBAPP_DEBUG_MODE_ENABLED=False

# Restart
docker-compose restart backend
```

---

## Secret Rotation Procedure

### TELEGRAM_BOT_API_SECRET

```bash
# 1. Generate
NEW_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
echo "New secret: $NEW_SECRET"

# 2. Update server .env

# 3. Update bot config

# 4. Restart backend
docker-compose restart backend

# 5. Smoke test
curl -X POST https://<DOMAIN>/api/v1/telegram/save-test/ \
  -H "X-Bot-Secret: $NEW_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"telegram_id": 123, "answers": {}}'
# Expected: 400 (validation) or 200, NOT 403
```

### TELEGRAM_BOT_TOKEN

```bash
# 1. @BotFather → /mybots → Revoke current token
# 2. Get new token
# 3. Update .env
# 4. Restart backend
# 5. ALL users must re-enter Mini App (old initData invalid)
```

---

## Escalation Matrix

| Инцидент | Primary | Secondary | Время реакции |
|----------|---------|-----------|---------------|
| Bot API 5xx | DevOps | Backend | 15 min |
| Auth 401 массово | Backend | DevOps | 30 min |
| Trainer Panel 403 | Backend | DevOps | 1 hour |
| Утечка секретов | DevOps + Security | — | IMMEDIATE |

### On-Call Runbook

```
1. Алерт → проверить docker-compose ps
2. Логи → docker logs backend --tail 100
3. 403/401 → проверить env переменные
4. 500 → escalate to Backend
5. Утечка → немедленно revoke + Security
```
