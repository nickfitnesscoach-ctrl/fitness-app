# 🔍 Полный аудит биллинга EatFit24 (End-to-End)

> **Дата аудита:** 2025-12-26  
> **Версия:** 3.1 (Post-Fix, single source of truth)  
> **Статус:** ✅ Production-Ready

---

## 📋 Executive Summary

Биллинг EatFit24 построен на production-grade архитектуре:
- **YooKassa** — платёжный провайдер
- **Django + DRF** — API + webhook endpoint
- **Celery + Redis** — асинхронная обработка webhook/renewals
- **React Context** — управление billing state на фронте

### ✅ Все P0/P1 задачи выполнены

| ID | Задача | Статус |
|----|--------|--------|
| A2 | Webhook XFF security (trust only from proxy) | ✅ Implemented |
| A3 | Idempotency на provider_event_id | ✅ Implemented |
| A4 | Observability (trace_id) | ✅ Implemented |
| A5 | Celery queue source of truth | ✅ Implemented |
| A6 | Frontend polling после оплаты | ✅ Implemented |
| A7 | Backend tests | ✅ Created |
| P2-1 | Payload sanitization | ✅ Implemented |

---

## 🏗️ Implemented Changes

### A2. Webhook Security (XFF Trust Guard)

**Файл:** `backend/apps/billing/webhooks/views.py`

**Изменения:**
- `_get_client_ip_secure()` возвращает `(effective_ip, remote_addr)`
- XFF доверяется **только** если `REMOTE_ADDR ∈ WEBHOOK_TRUSTED_PROXIES`
- попытки спуфинга логируются

```python
if trust_xff and _is_trusted_proxy(remote_addr):
    real_ip = xff.split(",")[0].strip()
else:
    real_ip = remote_addr
Acceptance Criteria:

✅ прямой запрос с поддельным XFF не проходит allowlist

✅ запрос через Nginx (trusted proxy) корректно вычисляет real_ip из XFF

A3. Idempotency на provider_event_id
Файлы:

backend/apps/billing/models.py — добавлено provider_event_id, UNIQUE на event_id

backend/apps/billing/webhooks/views.py — _extract_provider_event_id()

python
Копировать код
provider_event_id = models.CharField(
    "ID события от провайдера",
    max_length=255, null=True, blank=True, db_index=True,
)
event_id = models.CharField(
    "Idempotency key",
    max_length=255, unique=True,
)
Логика идемпотентности:

Primary: provider_event_id (если есть в payload YooKassa)

Fallback: {event_type}:{obj_id}:{obj_status}

Миграция: backend/apps/billing/migrations/0016_*.py

Acceptance Criteria:

✅ retry одного и того же события не создаёт дублей (200 OK)

✅ гонки закрыты уникальностью на уровне БД

A4. Observability (trace_id)
Файлы:

backend/apps/billing/webhooks/views.py

backend/apps/billing/webhooks/tasks.py

backend/apps/billing/webhooks/handlers.py

backend/apps/billing/models.py

Изменения:

trace_id = uuid.uuid4().hex[:8] генерируется на каждый входящий webhook

прокидывается в Celery task через kwargs

все ключевые логи содержат trace_id

Log Message	Точка
[WEBHOOK_RECEIVED] trace_id=...	вход webhook
[WEBHOOK_BLOCKED] trace_id=...	IP не в allowlist
[WEBHOOK_DUPLICATE] trace_id=...	повторный webhook
[WEBHOOK_QUEUED] trace_id=... task_id=...	enqueue
[WEBHOOK_TASK_START] trace_id=...	task start
[WEBHOOK_TASK_DONE] trace_id=... ok=true/false	task done

Acceptance Criteria:

✅ по trace_id восстанавливается цепочка end-to-end

✅ trace_id сохраняется в WebhookLog

A5. Celery Queue Source of Truth (SSOT)
Файл: backend/config/celery.py

SSOT:

default queue = default

billing tasks = billing

ai tasks = ai

python
Копировать код
app.conf.task_default_queue = "default"

app.conf.task_routes = {
    "apps.billing.webhooks.tasks.*": {"queue": "billing"},
    "apps.billing.tasks_recurring.*": {"queue": "billing"},
    "apps.ai.tasks.*": {"queue": "ai"},
}
Startup logging:

log_worker_queues() при старте worker’а

напоминание: worker MUST be started with -Q ai,billing,default

Acceptance Criteria:

✅ нет неоднозначности default vs celery

✅ в логах старта видно какие очереди слушаются

A6. Frontend Polling после оплаты
Файлы:

frontend/src/features/billing/hooks/usePaymentPolling.ts (NEW)

frontend/src/features/billing/hooks/useSubscriptionActions.ts (integration)

Поведение:

перед редиректом ставится localStorage flag

при возврате polling стартует автоматически

каждые 3 сек запрашивает /billing/me/

останавливается когда plan_code !== 'FREE'

таймаут 90 сек → показать кнопку “Обновить”

A7. Tests
Файл: backend/apps/billing/tests/test_webhook_improvements.py

Покрытие:

XFF trust guard + spoofing

provider_event_id extraction + idempotency

trace_id propagation

routing в очередь billing

payload sanitization

P2-1. Payload Sanitization
Файл: backend/apps/billing/webhooks/views.py

редактирование чувствительных данных перед сохранением raw_payload

✅ Gate Checklist (must-pass before “Production-Ready”)
Worker слушает очереди ai, billing, default

Webhook не блокируется (нет 403 / нет WEBHOOK_BLOCKED)

Webhook обрабатывается (есть WEBHOOK_TASK_DONE ok=true)

Миграции применены (migrate --check проходит)

Backend не доступен наружу на 8000 (только через Nginx)

✅ Verification Checklist
После деплоя
#	Проверка	Команда
1	Worker queues	docker compose exec -T celery-worker celery -A config inspect active_queues
2	Нет блокировок webhook	docker logs --tail=300 backend | grep WEBHOOK_BLOCKED
3	trace_id присутствует	docker logs --tail=300 celery-worker | grep trace_id
4	Миграции применены	docker compose exec -T backend python manage.py migrate --check
5	Backend port 8000 не торчит наружу	ss -lntp | grep :8000 + external nmap -p 8000 eatfit24.ru

🧪 E2E Payment Test
Создать тестовый платёж

Оплатить в YooKassa UI

Проверить WebhookLog:

bash
Копировать код
docker compose exec -T backend python manage.py shell -c "
from apps.billing.models import WebhookLog
log = WebhookLog.objects.order_by('-created_at').first()
print(f'trace_id={log.trace_id} status={log.status} provider_event_id={log.provider_event_id} event_id={log.event_id}')
"
📊 Architecture Diagram
mermaid
Копировать код
sequenceDiagram
    participant User
    participant Frontend
    participant Backend
    participant YooKassa
    participant Celery
    participant Redis

    User->>Frontend: Click "Buy PRO"
    Frontend->>Frontend: setPollingFlagForPayment()
    Frontend->>Backend: POST /billing/create-payment/
    Backend-->>Frontend: {confirmation_url}
    Frontend->>YooKassa: Redirect to payment
    User->>YooKassa: Complete payment
    YooKassa->>Backend: POST /webhooks/yookassa
    Note over Backend: Generate trace_id
    Backend->>Backend: _get_client_ip_secure()
    Note over Backend: Trust XFF only from trusted proxy
    Backend->>Backend: _extract_provider_event_id()
    Backend->>Backend: WebhookLog.get_or_create(event_id)
    Note over Backend: UNIQUE constraint = idempotency
    Backend->>Redis: Enqueue to 'billing' queue
    Backend-->>YooKassa: 200 OK
    Celery->>Redis: Consume from 'billing'
    Note over Celery: trace_id propagated
    Celery->>Backend: handle_yookassa_event(trace_id=...)
    Backend->>Backend: Payment.status = SUCCEEDED
    Backend->>Backend: activate_or_extend_subscription()
    User->>Frontend: Return to app
    Note over Frontend: Polling starts automatically
    Frontend->>Backend: GET /billing/me/ (every 3s)
    Backend-->>Frontend: {plan_code: "PRO_MONTHLY"}
    Note over Frontend: Polling stops, UI updates
📁 Files Changed (reference)
File	Changes
backend/apps/billing/webhooks/views.py	trace_id, provider_event_id, XFF guard, sanitization
backend/apps/billing/webhooks/handlers.py	trace_id parameter
backend/apps/billing/webhooks/tasks.py	trace_id parameter
backend/apps/billing/models.py	provider_event_id, trace_id, UNIQUE on event_id
backend/config/celery.py	task_routes, task_default_queue, startup logging
frontend/src/features/billing/hooks/usePaymentPolling.ts	NEW: polling hook
frontend/src/features/billing/hooks/useSubscriptionActions.ts	polling integration
backend/apps/billing/tests/test_webhook_improvements.py	NEW: tests
backend/apps/billing/migrations/0016_*.py	NEW: migration

🛡️ CHANGELOG
v3.0.0 (2025-12-26)
Added:

XFF trust guard (only from trusted proxies)

provider_event_id + DB idempotency

trace_id end-to-end

explicit Celery queues + routing (SSOT: default/billing/ai)

frontend polling after payment

tests + payload sanitization

✅ Production Ready
Все gate-условия выполнены:

✅ Webhook принимается и обрабатывается (очереди + безопасность)

✅ Надёжная идемпотентность на уровне event_id (UNIQUE constraint)

✅ Корреляция логов (trace_id)

✅ Фронт автообновляет статус после оплаты (polling)