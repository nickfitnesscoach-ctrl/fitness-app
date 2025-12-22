# PROD Smoke Tests — EatFit24

Минимальный набор тестов для проверки работоспособности PROD после деплоя.

---

## 1. Health Check

```bash
# С сервера
curl -i https://eatfit24.ru/health/

# Из контейнера
docker compose exec -T backend curl -sS http://localhost:8000/health/
```

**Ожидается:** `200 OK` + JSON `{"status": "ok"}` или аналог

---

## 2. Billing Plans (Public)

```bash
curl -i https://eatfit24.ru/api/v1/billing/plans/
```

**Ожидается:**
- Status: `200 OK`
- Body: JSON array с планами, например:
```json
[
  {"code": "FREE", "name": "Free", "price": "0.00", ...},
  {"code": "PRO_MONTHLY", "name": "PRO Monthly", "price": "299.00", ...}
]
```

**Если 404:** Проблема с nginx routing (`/api/v1/` не проксируется на backend)  
**Если 500:** Проблема с миграциями или БД

---

## 3. Telegram Auth Endpoint (Requires initData)

```bash
# Этот тест требует валидный initData из Telegram
# Для ручной проверки: открыть Mini App → DevTools → Network → найти запрос
curl -i -X POST https://eatfit24.ru/api/v1/telegram/users/get-or-create/ \
  -H "Content-Type: application/json" \
  -H "X-Telegram-Init-Data: <PASTE_REAL_INITDATA_HERE>"
```

**Ожидается:**
- Status: `200 OK` или `201 Created`
- Body: JSON с данными пользователя

**Если 401:** initData невалиден (проверь `TELEGRAM_BOT_TOKEN`)  
**Если 403:** CORS или другая защита

---

## 4. Billing Me (Requires Auth)

```bash
# Требует валидный initData
curl -i https://eatfit24.ru/api/v1/billing/me/ \
  -H "X-Telegram-Init-Data: <PASTE_REAL_INITDATA_HERE>"
```

**Ожидается:**
- Status: `200 OK`
- Body:
```json
{
  "plan_code": "FREE",
  "plan_name": "Free",
  "is_active": true,
  "daily_photo_limit": 3,
  "used_today": 0,
  "remaining_today": 3
}
```

**Если 401:** Auth не прошла — проблема с `TELEGRAM_BOT_TOKEN` или initData

---

## 5. CORS Check

```bash
curl -i -X OPTIONS https://eatfit24.ru/api/v1/billing/plans/ \
  -H "Origin: https://eatfit24.ru" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: X-Telegram-Init-Data"
```

**Ожидается:**
- `Access-Control-Allow-Origin: https://eatfit24.ru`
- `Access-Control-Allow-Headers` содержит `x-telegram-init-data`

---

## 6. ENV Check (внутри контейнера)

```bash
docker compose exec -T backend python -c "
import os
keys = [
    'DJANGO_SETTINGS_MODULE',
    'DEBUG',
    'ALLOWED_HOSTS',
    'CORS_ALLOWED_ORIGINS',
    'TELEGRAM_BOT_TOKEN',
    'YOOKASSA_MODE',
]
for k in keys:
    v = os.getenv(k)
    if k == 'TELEGRAM_BOT_TOKEN' and v:
        print(f'{k}: SET (starts with {v[:10]}...)')
    elif k == 'DEBUG':
        print(f'{k}: {v}')
    else:
        print(f'{k}: {\"SET\" if v else \"MISSING\"}')
"
```

**Критичные проверки:**
- `DJANGO_SETTINGS_MODULE` = `config.settings.production`
- `DEBUG` = `False`
- `TELEGRAM_BOT_TOKEN` = `SET`

---

## 7. Логи Backend

```bash
# Последние 100 строк
docker compose logs --tail=100 backend

# Фильтр по ошибкам auth
docker compose logs backend 2>&1 | grep -E "WebAppAuth|401|403|Unauthorized" | tail -20
```

**Что искать:**
- `[WebAppAuth] TELEGRAM_BOT_TOKEN is missing` → нет токена
- `[WebAppAuth] Hash mismatch` → неверный токен или испорченный initData
- `[WebAppAuth] initData expired` → clock skew на сервере
- `[SECURITY] DebugModeAuthentication used` → debug mode сработал (НЕ должно быть в PROD)

---

## 8. Time Sync Check

```bash
timedatectl status
```

**Ожидается:**
- NTP synchronized: yes
- Время близко к реальному (±1 минута)

---

## 9. Database Plans Check

```bash
docker compose exec -T backend python manage.py shell -c "
from apps.billing.models import SubscriptionPlan
plans = SubscriptionPlan.objects.filter(is_active=True, is_test=False)
for p in plans:
    print(f'{p.code}: {p.price} RUB (active={p.is_active})')
"
```

**Ожидается:**
- Минимум FREE план с `code=FREE`, `price=0`, `is_active=True`

---

## 10. Nginx Logs

```bash
# Если nginx в контейнере
docker compose logs --tail=50 frontend

# Если nginx на хосте
sudo tail -50 /var/log/nginx/error.log
```

**Что искать:**
- 502 Bad Gateway → backend не отвечает
- Connection refused → неверный upstream

---

## Quick Check Script

Создайте файл `smoke_test.sh`:

```bash
#!/bin/bash
set -e

BASE_URL="${1:-https://eatfit24.ru}"

echo "=== EatFit24 PROD Smoke Test ==="
echo "Target: $BASE_URL"
echo

echo "1. Health check..."
curl -sS "$BASE_URL/health/" | head -c 200
echo -e "\n✅ Health OK\n"

echo "2. Billing plans..."
PLANS=$(curl -sS "$BASE_URL/api/v1/billing/plans/" | head -c 500)
echo "$PLANS"
if echo "$PLANS" | grep -q "code"; then
    echo -e "✅ Plans OK\n"
else
    echo -e "❌ Plans FAILED\n"
    exit 1
fi

echo "=== All checks passed ==="
```

Запуск:
```bash
chmod +x smoke_test.sh
./smoke_test.sh https://eatfit24.ru
```

---

## Troubleshooting

| Симптом | Вероятная причина | Проверка |
|---------|-------------------|----------|
| Все 401 | `TELEGRAM_BOT_TOKEN` отсутствует | ENV check (#6) |
| Все 401 | Nginx не прокидывает `X-Telegram-Init-Data` | Nginx config |
| Plans 200, Me 401 | initData не отправляется | Browser DevTools |
| Все 502 | Backend не стартует | `docker compose ps`, logs |
| Все 404 | Nginx routing сломан | Nginx config, logs |
| CORS error в browser | `CORS_ALLOWED_ORIGINS` неверный | CORS check (#5) |

---

## 🚨 Pre-Deploy Checklist (5 пунктов)

> **Обязательно проверить ПЕРЕД каждым деплоем в PROD**

### 1. ✅ TELEGRAM_BOT_TOKEN задан
```bash
docker compose exec backend printenv TELEGRAM_BOT_TOKEN | head -c 15
# Должно вывести начало токена, например: 1234567890:ABC
```

### 2. ✅ Nginx прокидывает X-Telegram-Init-Data
```bash
grep -n "X-Telegram-Init-Data" frontend/nginx.conf
# Должно быть: proxy_set_header X-Telegram-Init-Data $http_x_telegram_init_data;
# НЕ должно быть: X-TG-INIT-DATA (это была причина бага!)
```

### 3. ✅ CORS разрешает header
```bash
docker compose exec backend python -c "
from django.conf import settings
print('x-telegram-init-data' in settings.CORS_ALLOW_HEADERS)
"
# Должно вывести: True
```

### 4. ✅ В БД есть планы
```bash
docker compose exec backend python manage.py shell -c "
from apps.billing.models import SubscriptionPlan
print(SubscriptionPlan.objects.filter(is_active=True, is_test=False).count())
"
# Должно быть >= 1
```

### 5. ✅ Время синхронизировано
```bash
timedatectl | grep -E "synchronized|Local time"
# NTP synchronized: yes
# Время должно быть актуальным (±1 минута)
```

---

## Quick Verification Script

Используйте готовый скрипт:
```bash
./scripts/smoke_test.sh https://eatfit24.ru
```
