# Telegram Backend — DevOps

| | |
|---|---|
| **Статус** | production-ready |
| **SSOT** | Environment variables, deploy checklist |
| **Обновлено** | 2024-12-16 |
| **Python** | 3.12 (см. `backend/Dockerfile`) |

> Операционная документация для деплоя, проверки и эксплуатации `apps/telegram/`.
> Инциденты → [ops_runbook.md](./ops_runbook.md) | Логи → [observability.md](./observability.md)

---

## 1. Environment Variables (SSOT)

> [!IMPORTANT]
> Все значения ниже — плейсхолдеры. **НИКОГДА** не коммитить реальные токены.

| Переменная | Required | DEV | PROD | Если не задана |
|------------|----------|-----|------|----------------|
| `TELEGRAM_BOT_TOKEN` | ✅ | ✅ | ✅ | initData → 401 |
| `TELEGRAM_BOT_API_SECRET` | ⚠️ | ❌ | ✅ | Bot API без защиты |
| `TELEGRAM_ADMINS` | ⚠️ | ❌ | ✅ | PROD: никто не админ |
| `WEBAPP_DEBUG_MODE_ENABLED` | ❌ | True | **False** | — |
| `PERSONAL_PLAN_DAILY_LIMIT` | ❌ | 3 | 3 | — |

### Формат .env

```bash
# Placeholders — заменить на реальные значения
TELEGRAM_BOT_TOKEN=<TELEGRAM_BOT_TOKEN>
TELEGRAM_BOT_API_SECRET=<TELEGRAM_BOT_API_SECRET>
TELEGRAM_ADMINS=<TELEGRAM_ADMIN_IDS>
```

### Secrets Redaction Rules

| ❌ Запрещено | Почему |
|--------------|--------|
| Логировать секреты | Утечка через логи |
| Писать в код/документацию | Утечка через git |
| Передавать в URL/query params | Access logs |
| Скриншоты с секретами | Утечка через изображения |

**Минимальная длина `TELEGRAM_BOT_API_SECRET`:** 32 символа

**Генерация:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## 2. Pre-Deploy Checklist (Go/No-Go)

> [!CAUTION]
> Деплой запрещён если любой пункт ❌

| # | Check | Command | Expected |
|---|-------|---------|----------|
| 1 | DEBUG off | `python manage.py shell -c "from django.conf import settings; print(settings.DEBUG)"` | `False` |
| 2 | Debug mode off | `python manage.py shell -c "from django.conf import settings; print(getattr(settings, 'WEBAPP_DEBUG_MODE_ENABLED', False))"` | `False` |
| 3 | Bot token set | `python manage.py shell -c "from django.conf import settings; assert settings.TELEGRAM_BOT_TOKEN"` | No error |
| 4 | API secret set (32+) | `python manage.py shell -c "from django.conf import settings; assert len(settings.TELEGRAM_BOT_API_SECRET or '') >= 32"` | No error |
| 5 | Admins set | `python manage.py shell -c "from django.conf import settings; assert settings.TELEGRAM_ADMINS"` | No error |
| 6 | Migrations OK | `python manage.py migrate --check` | No output |
| 7 | URLs load | `python -c "from apps.telegram.urls import urlpatterns"` | No error |

### Automated Script

```bash
#!/bin/bash
# pre_deploy_telegram.sh
set -e

echo "[1/7] DEBUG..."
python manage.py shell -c "from django.conf import settings; assert not settings.DEBUG"

echo "[2/7] WEBAPP_DEBUG_MODE..."
python manage.py shell -c "from django.conf import settings; assert not getattr(settings, 'WEBAPP_DEBUG_MODE_ENABLED', False)"

echo "[3/7] TELEGRAM_BOT_TOKEN..."
python manage.py shell -c "from django.conf import settings; assert settings.TELEGRAM_BOT_TOKEN"

echo "[4/7] TELEGRAM_BOT_API_SECRET (32+)..."
python manage.py shell -c "from django.conf import settings; assert len(settings.TELEGRAM_BOT_API_SECRET or '') >= 32"

echo "[5/7] TELEGRAM_ADMINS..."
python manage.py shell -c "from django.conf import settings; assert settings.TELEGRAM_ADMINS"

echo "[6/7] Migrations..."
python manage.py migrate --check

echo "[7/7] URLs..."
python -c "from apps.telegram.urls import urlpatterns"

echo "✓ ALL CHECKS PASSED — deploy OK"
```

---

## 3. CI/CD: Telegram Job

```yaml
# .github/workflows/ci.yml или .gitlab-ci.yml
telegram_checks:
  stage: test
  script:
    # Django checks
    - python manage.py check --deploy
    - python manage.py migrate --check
    
    # Tests
    - pytest apps/telegram/ -q
    
    # Syntax (prevents CI failures on bad imports)
    - python -m py_compile apps/telegram/urls.py
    - python -m py_compile apps/telegram/auth/views.py
    - python -m py_compile apps/telegram/bot/views.py
    - python -m py_compile apps/telegram/trainer_panel/views.py
    
    # URL import check
    - python -c "from apps.telegram.urls import urlpatterns"
    
    # Secrets leak check
    - "! grep -rE '[0-9]{8,}:[A-Za-z0-9_-]{20,}' apps/telegram/"
    - "! grep -rE 'TELEGRAM_BOT_TOKEN=[^<]' apps/telegram/"
    - "! grep -rE 'BOT_API_SECRET=[^<]' apps/telegram/"
```

### Secrets Leak Detection (CI)

```bash
# Проверка на случайно закоммиченные токены
# Паттерн bot token: 1234567890:ABCdef...

grep -rE '[0-9]{8,}:[A-Za-z0-9_-]{20,}' apps/telegram/
# Должен быть ПУСТОЙ вывод

grep -rE 'TELEGRAM_BOT_TOKEN=[^<\$]' apps/telegram/
# Должен быть ПУСТОЙ вывод (только плейсхолдеры <...> или $VAR)
```

---

## 4. Docker Compose Health Checks

```yaml
# docker-compose.yml
services:
  backend:
    build: ./backend
    environment:
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - TELEGRAM_BOT_API_SECRET=${TELEGRAM_BOT_API_SECRET}
      - TELEGRAM_ADMINS=${TELEGRAM_ADMINS}
    healthcheck:
      test: ["CMD", "python", "manage.py", "check", "--deploy"]
      interval: 30s
      timeout: 10s
      retries: 3
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy

  db:
    image: postgres:15
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
```

### Health Endpoint (если нужен HTTP)

```python
# apps/core/views.py или urls.py
from django.http import JsonResponse

def health_check(request):
    return JsonResponse({"status": "ok"})

# urls.py
path('api/v1/health/', health_check),
```

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health/"]
```

---

## 5. Post-Deploy Smoke Tests

> Копипасти и выполняй. Замени `<DOMAIN>`, `<INIT_DATA>`, `<SECRET>`.

### WebApp Auth

```bash
# ✅ С валидным initData → 200
curl -s -o /dev/null -w "%{http_code}" \
  -X POST https://<DOMAIN>/api/v1/telegram/auth/ \
  -H "Content-Type: application/json" \
  -H "X-Telegram-Init-Data: <VALID_INIT_DATA>"
# Expected: 200

# ❌ Без initData → 401
curl -s -o /dev/null -w "%{http_code}" \
  -X POST https://<DOMAIN>/api/v1/telegram/auth/ \
  -H "Content-Type: application/json"
# Expected: 401
```

### Bot API

```bash
# ❌ Без секрета → 403
curl -s -o /dev/null -w "%{http_code}" \
  -X POST https://<DOMAIN>/api/v1/telegram/save-test/ \
  -H "Content-Type: application/json" \
  -d '{"telegram_id": 123}'
# Expected: 403

# ✅ С секретом → 400 (validation) или 200
curl -s -o /dev/null -w "%{http_code}" \
  -X POST https://<DOMAIN>/api/v1/telegram/save-test/ \
  -H "Content-Type: application/json" \
  -H "X-Bot-Secret: <TELEGRAM_BOT_API_SECRET>" \
  -d '{"telegram_id": 123, "answers": {}}'
# Expected: 400 или 200 (НЕ 403)

# ✅ Public endpoint → 200
curl -s -o /dev/null -w "%{http_code}" \
  https://<DOMAIN>/api/v1/telegram/invite-link/
# Expected: 200
```

### Trainer Panel

```bash
# ✅ Админ → 200
curl -s -o /dev/null -w "%{http_code}" \
  -X GET https://<DOMAIN>/api/v1/telegram/applications/ \
  -H "X-Telegram-Init-Data: <ADMIN_INIT_DATA>"
# Expected: 200

# ❌ Не-админ → 403
curl -s -o /dev/null -w "%{http_code}" \
  -X GET https://<DOMAIN>/api/v1/telegram/applications/ \
  -H "X-Telegram-Init-Data: <NON_ADMIN_INIT_DATA>"
# Expected: 403
```

### All-in-One Script

```bash
#!/bin/bash
# smoke_test_telegram.sh
DOMAIN="your-domain.com"
SECRET="<TELEGRAM_BOT_API_SECRET>"

echo "Testing Bot API without secret..."
CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST https://$DOMAIN/api/v1/telegram/save-test/ \
  -H "Content-Type: application/json" \
  -d '{"telegram_id": 123}')
[ "$CODE" = "403" ] && echo "✓ 403 OK" || echo "✗ Expected 403, got $CODE"

echo "Testing public endpoint..."
CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  https://$DOMAIN/api/v1/telegram/invite-link/)
[ "$CODE" = "200" ] && echo "✓ 200 OK" || echo "✗ Expected 200, got $CODE"
```

---

## 6. Key Alerts

| Метрика | Threshold | Action |
|---------|-----------|--------|
| 401/403 spike на telegram/* | > 10/min | Проверить env |
| 5xx на telegram endpoints | > 1/min | Escalate to Backend |
| Debug mode auth used | ANY | 🔴 IMMEDIATE fix |

**Grep для алертов:**
```bash
# Security — любое появление = тревога
docker logs backend 2>&1 | grep -iE "(debug mode|hash mismatch|Bot-Secret invalid)"
```

→ Подробнее: [observability.md](./observability.md)

---

## 7. Quick Reference

```
┌─────────────────────────────────────────────────────────────┐
│                 TELEGRAM DEVOPS QUICK REF                    │
├─────────────────────────────────────────────────────────────┤
│ ENV (PROD required):                                         │
│   TELEGRAM_BOT_TOKEN=<TELEGRAM_BOT_TOKEN>                   │
│   TELEGRAM_BOT_API_SECRET=<TELEGRAM_BOT_API_SECRET>         │
│   TELEGRAM_ADMINS=<TELEGRAM_ADMIN_IDS>                      │
│                                                              │
│ FORBIDDEN in PROD:                                           │
│   DEBUG=True                                                 │
│   WEBAPP_DEBUG_MODE_ENABLED=True                            │
│                                                              │
│ Smoke tests:                                                 │
│   /save-test/ no secret → 403                               │
│   /invite-link/ → 200                                        │
│   /applications/ + admin → 200                              │
│                                                              │
│ Incidents → ops_runbook.md                                   │
│ Logs → observability.md                                      │
└─────────────────────────────────────────────────────────────┘
```

---

## Related Docs

| Doc | Содержание |
|-----|------------|
| [ops_runbook.md](./ops_runbook.md) | Инциденты, disaster recovery, escalation |
| [observability.md](./observability.md) | Логи, алерты, метрики |
| [03_auth_and_security.md](./03_auth_and_security.md) | Security model (для разработчиков) |
