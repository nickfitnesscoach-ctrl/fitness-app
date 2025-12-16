# Telegram Observability & Alerts

| | |
|---|---|
| **Статус** | production-ready |
| **SSOT** | Логирование и мониторинг |
| **Обновлено** | 2024-12-16 |

---

## Loggers

| Logger | Компонент |
|--------|-----------|
| `apps.telegram.auth` | WebApp authentication, initData |
| `apps.telegram.bot` | Bot API, X-Bot-Secret |
| `apps.telegram.trainer_panel` | Admin panel access |

---

## Log Levels

| Level | Когда |
|-------|-------|
| `DEBUG` | Детали валидации (только DEV) |
| `INFO` | Успешные операции |
| `WARNING` | Security denials, fallbacks |
| `ERROR` | Exceptions, DB errors |
| `CRITICAL` | Service down, секреты недоступны |

---

## Critical Events (MUST be logged)

| Event | Level | Пример строки |
|-------|-------|---------------|
| Invalid initData | WARNING | `initData validation failed: hash mismatch` |
| Bot API 403 | WARNING | `X-Bot-Secret invalid or missing` |
| Trainer Panel denied | WARNING | `Admin access denied for telegram_id=...` |
| Debug Mode used | WARNING | `[SECURITY] Debug mode authentication USED` |
| User created | INFO | `TelegramUser created: telegram_id=...` |
| Plan limit exceeded | INFO | `Personal plan daily limit reached` |

---

## Where to Find Logs

| Среда | Команда |
|-------|---------|
| Docker dev | `docker logs backend` |
| Docker prod | `docker-compose logs -f backend` |
| Kubernetes | `kubectl logs -f deployment/backend` |

### Useful Grep Commands

```bash
# Telegram errors
docker logs backend 2>&1 | grep -E "(telegram|initData|Bot-Secret)" | tail -50

# Security warnings
docker logs backend 2>&1 | grep -i "warning" | grep -i telegram

# Real-time auth
docker logs -f backend 2>&1 | grep "telegram.auth"

# Debug mode usage (SHOULD BE EMPTY IN PROD)
docker logs backend 2>&1 | grep -i "debug mode"
```

---

## Alert Thresholds (Minimum)

| Метрика | Threshold | Severity |
|---------|-----------|----------|
| 401/403 spike на `/api/v1/telegram/*` | > 10/min | ⚠️ Warning |
| 5xx rate на telegram endpoints | > 1/min | 🔴 Critical |
| Auth latency p95 | > 500ms | ⚠️ Warning |
| Debug mode auth used | ANY in PROD | 🔴 Critical |

---

## Alerting Patterns

### Trevious Log Lines (grep for alerts)

```bash
# Security alerts — любое появление = тревога
grep -E "(Debug mode authentication|hash mismatch|Bot-Secret invalid)" logs.txt

# Spike detection (count per minute)
docker logs backend --since 1m 2>&1 | grep -c "403"
```

### Prometheus Metrics (если есть)

```python
# Рекомендуемые метрики
telegram_auth_total{status="success|failure"}
telegram_bot_api_requests{endpoint, status}
telegram_trainer_panel_access{result="allowed|denied"}
```

---

## Dashboards (рекомендации)

### Grafana Panels

1. **Auth Success Rate** — `telegram_auth_total{status="success"} / telegram_auth_total`
2. **Bot API Errors** — rate of 403/500 on `/save-test/`, `/personal-plan/*`
3. **Trainer Panel Access** — allowed vs denied ratio
4. **Debug Mode Usage** — should be 0 in PROD

---

## Incident Log Template

```
Date: YYYY-MM-DD HH:MM
Severity: Critical | Warning | Info
Component: auth | bot | trainer_panel
Summary: <one line>
Root Cause: <one line>
Resolution: <steps taken>
Duration: <minutes>
```
