# Billing Security Fixes — Журнал изменений

> **Дата:** 2024-12-17  
> **Версия:** 1.0

---

## [PRIORITY 1] Throttles для платёжных эндпоинтов

**Файлы:**  
- [views.py](file:///d:/NICOLAS/1_PROJECTS/_IT_Projects/Fitness-app/backend/apps/billing/views.py)
- [webhooks/views.py](file:///d:/NICOLAS/1_PROJECTS/_IT_Projects/Fitness-app/backend/apps/billing/webhooks/views.py)

**Суть проблемы:**  
Throttle-классы (`PaymentCreationThrottle`, `WebhookThrottle`) были определены в `throttles.py`, но НЕ применялись ни к одному view. Это позволяло спамить эндпоинты создания платежей.

**Исправление:**  
```python
# views.py — добавлено ко всем payment endpoints:
@throttle_classes([PaymentCreationThrottle])  # 20 req/hour
def create_payment(request): ...

# webhooks/views.py — конвертирован в DRF view:
@api_view(["POST"])
@throttle_classes([WebhookThrottle])  # 100 req/hour
def yookassa_webhook(request): ...
```

**Результат:**  
- `create_payment`, `bind_card_start`, `create_test_live_payment`, `create_plus_payment`, `subscribe` — лимит 20/час
- `yookassa_webhook` — лимит 100/час

---

## [PRIORITY 1] Защита webhook от XFF spoofing

**Файлы:**  
- [webhooks/views.py](file:///d:/NICOLAS/1_PROJECTS/_IT_Projects/Fitness-app/backend/apps/billing/webhooks/views.py)
- [base.py](file:///d:/NICOLAS/1_PROJECTS/_IT_Projects/Fitness-app/backend/config/settings/base.py)

**Суть проблемы:**  
`X-Forwarded-For` доверялся безусловно. Атакующий мог подделать заголовок, чтобы обойти IP allowlist.

**Исправление:**  
```python
# settings/base.py — новая настройка:
WEBHOOK_TRUST_XFF = os.environ.get("WEBHOOK_TRUST_XFF", "false").lower() == "true"

# webhooks/views.py — новая функция:
def _get_client_ip_secure(request):
    trust_xff = getattr(settings, "WEBHOOK_TRUST_XFF", False)
    if trust_xff:
        # ... берём из XFF
    return request.META.get("REMOTE_ADDR")  # default: только REMOTE_ADDR
```

**Результат:**  
По умолчанию XFF игнорируется. Включать `WEBHOOK_TRUST_XFF=true` только при trusted proxy.

---

## [PRIORITY 2] Race condition в дневных лимитах

**Файлы:**  
- [usage.py](file:///d:/NICOLAS/1_PROJECTS/_IT_Projects/Fitness-app/backend/apps/billing/usage.py)
- [ai/views.py](file:///d:/NICOLAS/1_PROJECTS/_IT_Projects/Fitness-app/backend/apps/ai/views.py)

**Суть проблемы:**  
Проверка лимита и инкремент были раздельны. 10 параллельных запросов могли все пройти проверку.

**Исправление:**  
```python
# usage.py — новый метод:
def check_and_increment_if_allowed(self, user, limit, amount=1):
    with transaction.atomic():
        usage = self.select_for_update().get_or_create(...)
        if current_count >= limit:
            return (False, current_count)  # НЕ увеличиваем
        self.filter(pk=usage.pk).update(F("photo_ai_requests") + amount)
        return (True, current_count + amount)

# ai/views.py — используем атомарный метод:
allowed, used_count = DailyUsage.objects.check_and_increment_if_allowed(...)
```

**Результат:**  
Проверка + инкремент атомарны. Race condition невозможен.

---

## [PRIORITY 2] Блокировка is_test=True планов

**Файл:**  
- [serializers.py](file:///d:/NICOLAS/1_PROJECTS/_IT_Projects/Fitness-app/backend/apps/billing/serializers.py)

**Суть проблемы:**  
Test-планы (например `TEST_LIVE`) могли быть использованы через обычный `/create-payment/`.

**Исправление:**  
```python
def _get_plan_by_code_or_legacy(plan_code):
    return SubscriptionPlan.objects.get(
        code=plan_code, 
        is_active=True, 
        is_test=False  # <-- ДОБАВЛЕНО
    )
```

**Результат:**  
Test-планы доступны ТОЛЬКО через admin endpoint (`create_test_live_payment`).

---

## [PRIORITY 3] Валидация return_url

**Файлы:**  
- [views.py](file:///d:/NICOLAS/1_PROJECTS/_IT_Projects/Fitness-app/backend/apps/billing/views.py)
- [base.py](file:///d:/NICOLAS/1_PROJECTS/_IT_Projects/Fitness-app/backend/config/settings/base.py)

**Суть проблемы:**  
Open redirect: атакующий мог передать `return_url=https://evil.com` и перенаправить пользователя после оплаты.

**Исправление:**  
```python
# settings/base.py:
ALLOWED_RETURN_URL_DOMAINS = ["eatfit24.ru", "localhost", "127.0.0.1"]

# views.py — новая функция + применена к 5 endpoints:
def _validate_return_url(url, request):
    hostname = urlparse(url).hostname
    if hostname not in allowed_domains:
        return _build_default_return_url(request)  # fallback
    return url
```

**Результат:**  
Redirect только на разрешённые домены.

---

## [PRIORITY 3] Пометка дублирующего клиента как deprecated

**Файл:**  
- [yookassa_client.py](file:///d:/NICOLAS/1_PROJECTS/_IT_Projects/Fitness-app/backend/apps/billing/yookassa_client.py)

**Суть проблемы:**  
Два YooKassa клиента в проекте создавали путаницу.

**Исправление:**  
Добавлен deprecation notice в docstring:
```python
"""
[DEPRECATED 2024-12]
Используйте YooKassaService из services.py.
"""
```

**Результат:**  
SDK-клиент (`services.py`) — единственный рекомендуемый. `yookassa_client.py` останется для совместимости.

---

## Новые настройки в settings

| Настройка | Default | Описание |
|-----------|---------|----------|
| `WEBHOOK_TRUST_XFF` | `false` | Доверять X-Forwarded-For (только за trusted proxy) |
| `ALLOWED_RETURN_URL_DOMAINS` | `eatfit24.ru,localhost,127.0.0.1` | Whitelist доменов для return_url |
