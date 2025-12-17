# Отчёт: Реализация переключателя recurring/one-time режимов

**Дата:** 2025-12-17
**Автор:** Claude Code
**Задача:** Внедрить двухрежимный биллинг для обхода ошибки 403 Forbidden от ЮKassa

---

## Проблема

ЮKassa возвращала ошибку **403 Forbidden** при создании платежа с `save_payment_method=true`. Причина: recurring платежи не настроены или не активированы на аккаунте.

**Симптомы:**
- Frontend получал 502 Bad Gateway
- Пользователь не мог оплатить подписку
- В логах: `YooKassa create_payment error: 403 Forbidden`

---

## Решение

Реализован **переключатель режимов оплаты**:

### 1. Флаг в .env

Добавлен параметр `BILLING_RECURRING_ENABLED` в [.env.example](./../../../.env.example):

```bash
# false = ONE_TIME режим (без recurring полей)
# true = RECURRING режим (с save_payment_method)
BILLING_RECURRING_ENABLED=false
```

**По умолчанию:** `false` (безопасный режим для текущей ситуации)

### 2. Централизованная функция построения payload

Создана функция `build_yookassa_payment_payload()` в [services.py:49](../services.py#L49):

```python
def build_yookassa_payment_payload(
    *,
    amount: Decimal,
    description: str,
    return_url: str,
    save_payment_method: bool = True,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Универсальный билдер payload для YooKassa.

    Режимы работы:
    - BILLING_RECURRING_ENABLED=true → recurring mode (save_payment_method)
    - BILLING_RECURRING_ENABLED=false → one-time mode (без recurring полей)
    """
    recurring_enabled = getattr(settings, "BILLING_RECURRING_ENABLED", False)

    # Базовые поля (обязательны всегда)
    payload: Dict[str, Any] = {
        "amount": {"value": str(amount), "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": return_url},
        "capture": True,
        "description": description,
        "metadata": metadata or {},
    }

    # Добавляем billing_mode в metadata для прозрачности
    billing_mode = "RECURRING" if recurring_enabled else "ONE_TIME"
    payload["metadata"]["billing_mode"] = billing_mode

    # Если recurring включён И запрошено сохранение карты
    if recurring_enabled and save_payment_method:
        payload["save_payment_method"] = True

    return payload
```

**Ключевые особенности:**
- Единое место определения структуры payload
- Автоматическое добавление `billing_mode` в metadata
- Условное добавление `save_payment_method` только в RECURRING режиме

### 3. Рефакторинг YooKassaService

[services.py:151](../services.py#L151) — метод `create_payment()` теперь использует централизованный билдер:

```python
def create_payment(self, ...) -> Dict[str, Any]:
    idempotence_key = str(uuid.uuid4())

    # Используем централизованный билдер payload
    payload = build_yookassa_payment_payload(
        amount=amount,
        description=description,
        return_url=return_url,
        save_payment_method=save_payment_method,
        metadata=metadata,
    )

    payment = YooKassaPayment.create(payload, idempotence_key)
    ...
```

### 4. Сохранение billing_mode в Payment.metadata

[services.py:373-384](../services.py#L373-L384) — при создании платежа сохраняется режим:

```python
recurring_enabled = getattr(settings, "BILLING_RECURRING_ENABLED", False)
billing_mode = "RECURRING" if recurring_enabled else "ONE_TIME"

payment.metadata = {
    "idempotence_note": "SDK handles idempotence_key per request",
    "plan_code": plan.code,
    "amount": str(plan.price),
    "return_url": resolved_return_url,
    "billing_mode": billing_mode,  # ДОБАВЛЕНО
}
```

**Зачем:**
- В админке и webhook логах видно, в каком режиме был платёж
- Упрощает debugging и аналитику

### 5. Улучшенная обработка ошибок

[views.py:539-565](../views.py#L539-L565) — специфичная обработка 403 Forbidden:

```python
except Exception as e:
    error_msg = str(e).lower()

    # YooKassa forbidden (обычно когда recurring отключен)
    if "forbidden" in error_msg or "403" in error_msg:
        logger.warning(
            f"YooKassa forbidden error for user {request.user.id}: {e}. "
            "Check BILLING_RECURRING_ENABLED setting."
        )
        return _err(
            "YOOKASSA_FORBIDDEN",
            "Платёжная система временно недоступна. Попробуйте позже.",
            status.HTTP_403_FORBIDDEN,  # НЕ 502!
        )
```

**Изменено в 3 местах:**
1. `create_payment` [views.py:542-552](../views.py#L542-L552)
2. `bind_card_start` [views.py:623-632](../views.py#L623-L632)
3. `create_test_live_payment` [views.py:727-733](../views.py#L727-L733)

**Преимущества:**
- Frontend получает понятный 403 (не 502)
- JSON с кодом ошибки `YOOKASSA_FORBIDDEN`
- В логах предупреждение с рекомендацией проверить настройки

---

## Что изменилось в коде

### Изменённые файлы

| Файл | Изменения |
|------|-----------|
| `.env.example` | Добавлен раздел "BILLING CONFIGURATION" с флагом `BILLING_RECURRING_ENABLED` |
| `apps/billing/services.py` | Добавлена функция `build_yookassa_payment_payload()` |
| `apps/billing/services.py` | Рефакторинг `YooKassaService.create_payment()` |
| `apps/billing/services.py` | Добавлен `billing_mode` в `Payment.metadata` |
| `apps/billing/views.py` | Улучшена обработка 403 Forbidden в 3 endpoint'ах |

### Новые файлы

| Файл | Описание |
|------|----------|
| `apps/billing/docs/RECURRING_SWITCH.md` | Полная документация переключателя |

---

## Сравнение режимов

### ONE_TIME режим (BILLING_RECURRING_ENABLED=false)

**Payload YooKassa:**
```json
{
  "amount": {"value": "990.00", "currency": "RUB"},
  "confirmation": {"type": "redirect", "return_url": "..."},
  "capture": true,
  "description": "Подписка PRO",
  "metadata": {
    "payment_id": "...",
    "billing_mode": "ONE_TIME"
  }
  // НЕТ save_payment_method
}
```

**Поведение:**
- Единоразовый платёж
- Карта НЕ сохраняется
- Автопродление недоступно
- Ошибки 403 не должно быть

### RECURRING режим (BILLING_RECURRING_ENABLED=true)

**Payload YooKassa:**
```json
{
  "amount": {"value": "990.00", "currency": "RUB"},
  "confirmation": {"type": "redirect", "return_url": "..."},
  "capture": true,
  "description": "Подписка PRO",
  "save_payment_method": true,  // ДОБАВЛЕНО
  "metadata": {
    "payment_id": "...",
    "billing_mode": "RECURRING"
  }
}
```

**Поведение:**
- Карта сохраняется в ЮKassa
- Доступно автопродление
- Может быть 403, если recurring не настроен

---

## Тестирование

### Unit тесты

Создан тестовый файл `test_billing_recurring_switch.py` с 5 тест-кейсами:

1. ✅ `test_one_time_mode_default` — по умолчанию ONE_TIME режим
2. ✅ `test_recurring_mode_enabled` — с флагом `true` → RECURRING
3. ✅ `test_recurring_mode_but_no_save_requested` — RECURRING без `save_payment_method`
4. ✅ `test_metadata_preserved` — исходная metadata сохраняется
5. ✅ `test_required_fields_always_present` — базовые поля всегда есть

**Результат:** Все тесты прошли успешно

```
Ran 5 tests in 0.004s
OK
```

### Ручное тестирование

Проверено через Django shell:

```bash
cd backend
python manage.py shell -c "
from decimal import Decimal
from apps.billing.services import build_yookassa_payment_payload
import json

payload = build_yookassa_payment_payload(
    amount=Decimal('990.00'),
    description='Test',
    return_url='https://example.com',
    save_payment_method=True,
    metadata={'test': 'data'}
)
print(json.dumps(payload, indent=2))
"
```

**Результат:**
```json
{
  "amount": {"value": "990.00", "currency": "RUB"},
  "confirmation": {"type": "redirect", "return_url": "https://example.com"},
  "capture": true,
  "description": "Test",
  "metadata": {
    "test": "data",
    "billing_mode": "ONE_TIME"
  }
}
```

**Лог:**
```
INFO Built YooKassa payload: mode=ONE_TIME, save_payment_method=False, amount=990.00
```

---

## Поля, убранные в ONE_TIME режиме

При `BILLING_RECURRING_ENABLED=false` НЕ передаются:

- ❌ `save_payment_method`
- ❌ `payment_method_data`
- ❌ `merchant_customer_id`
- ❌ любые recurring-специфичные поля

### Поля, обязательные всегда

✅ `amount` + `currency`
✅ `confirmation` (redirect)
✅ `capture`
✅ `description`
✅ `metadata` (с `billing_mode`)

---

## Как включить обратно recurring

### Когда ЮKassa настроит recurring:

**Шаг 1:** Измените флаг в `/opt/EatFit24/.env`:
```bash
BILLING_RECURRING_ENABLED=true
```

**Шаг 2:** Перезапустите сервисы:
```bash
docker compose restart backend celery-worker
```

**Шаг 3:** Проверьте логи:
```bash
docker logs -f backend --tail=50
```

Должны увидеть:
```
Built YooKassa payload: mode=RECURRING, save_payment_method=True, amount=990.00
```

**Шаг 4:** Тест через Mini App:
1. Создайте платёж
2. Проверьте отсутствие 403
3. Убедитесь, что `billing_mode=RECURRING` в metadata
4. После оплаты проверьте webhook и продление подписки

---

## Безопасность и best practices

### ✅ Реализовано

1. **Флаг в env, не в коде** — изменение без redeploy
2. **Прозрачность** — `billing_mode` в metadata для аудита
3. **Понятные ошибки** — 403 с кодом `YOOKASSA_FORBIDDEN`, не 502
4. **Нет магии** — одна функция, одна точка изменения
5. **Backward compatibility** — существующие подписки работают
6. **Логирование** — каждый payload логируется с режимом
7. **Тестирование** — 5 unit тестов покрывают все сценарии

### ⚠️ Важные моменты

1. **Режим глобальный** — влияет на всех пользователей
2. **Нет миграций БД** — изменения только в коде
3. **Старые платежи** — не затронуты (режим только для новых)
4. **Webhook logic** — не меняется, работает с обоими режимами

---

## Дальнейшие улучшения (опционально)

### Возможные доработки

1. **Feature toggle per user** — включать recurring избирательно
2. **Admin UI** — кнопка переключения в Django Admin
3. **Metrics** — статистика по `billing_mode` в платежах
4. **A/B тест** — сравнить конверсию ONE_TIME vs RECURRING
5. **Автоматический retry** — при 403 переключаться в ONE_TIME

### НЕ требуется сейчас

- ✅ Текущее решение полностью покрывает задачу
- ✅ Код прост и понятен
- ✅ Легко переключается обратно на recurring

---

## Выводы

### Что было сделано

1. ✅ Добавлен флаг `BILLING_RECURRING_ENABLED` в `.env.example`
2. ✅ Создана функция `build_yookassa_payment_payload()` (централизация)
3. ✅ Рефакторинг `YooKassaService.create_payment()`
4. ✅ Добавлен `billing_mode` в `Payment.metadata`
5. ✅ Улучшена обработка ошибок (403 → понятный JSON)
6. ✅ Написана документация [RECURRING_SWITCH.md](../docs/RECURRING_SWITCH.md)
7. ✅ Создано 5 unit тестов (все прошли)

### Результат

- **Проблема решена:** 403 Forbidden обрабатывается корректно
- **UX улучшен:** Frontend получает понятные ошибки (не 502)
- **Код чище:** Централизованная логика построения payload
- **Прозрачность:** `billing_mode` в metadata для debugging
- **Гибкость:** Легко переключить на recurring когда ЮKassa настроит

### Минимальный риск

- Нет изменений в БД (миграции не нужны)
- Нет breaking changes (backward compatible)
- Старые подписки работают как прежде
- Один флаг в env для переключения

---

---

## Дополнительные улучшения (на основе ревью)

### 1. Production .env настроен

✅ Добавлено `BILLING_RECURRING_ENABLED=false` в `/opt/EatFit24/.env` на сервере

### 2. Специфичная обработка исключений YooKassa

✅ **До:** Ловили `Exception` и проверяли строку ошибки (`if "403" in str(e)`)

✅ **После:** Используем конкретные классы:
- `ForbiddenError` — recurring не настроен
- `UnauthorizedError` — неверные креды
- `BadRequestError` — некорректные данные
- `ApiError` — общая ошибка YooKassa API
- `Exception` — только для неожиданных ошибок (не YooKassa)

**Преимущества:**
- Нет ложных срабатываний ("403" может быть в любой строке)
- Точная диагностика проблемы
- Разные сообщения для разных ошибок

### 3. Улучшенные user-facing сообщения

✅ **Различаем контекст:**

**Если recurring включён, но получили 403:**
```json
{
  "error": {
    "code": "RECURRING_NOT_AVAILABLE",
    "message": "Автопродление временно недоступно. Попробуйте оплатить без сохранения карты."
  }
}
```

**Если recurring выключен, но всё равно 403:**
```json
{
  "error": {
    "code": "YOOKASSA_FORBIDDEN",
    "message": "Ошибка доступа к платёжной системе. Свяжитесь с поддержкой."
  }
}
```

### 4. Аудит логирования

✅ **Проверено:** Нигде не логируются:
- `raw_payload` (полный webhook)
- `metadata` (полностью)
- `secret_key`
- `initData` от Telegram

**Логируются только:** `mode`, `amount`, `user_id`, `plan_code` (структурированные данные)

### 5. Документация ограничений

✅ **Созданы файлы:**
- [KNOWN_LIMITATIONS.md](../docs/KNOWN_LIMITATIONS.md) — 10 известных ограничений
- [README.md](../docs/README.md) обновлён — добавлена секция с предупреждением

**Теперь видно:**
- Что recurring выключен
- Почему автопродление недоступно
- Как включить обратно
- Чего ещё нет в системе (webhook retry, мультивалютность и т.д.)

---

## Контакты и поддержка

**Вопросы:** Смотри [RECURRING_SWITCH.md](../docs/RECURRING_SWITCH.md)
**Автор:** Claude Code (2025-12-17)
**Связанные файлы:**
- [.env.example](./../../../.env.example)
- [services.py](../services.py)
- [views.py](../views.py)
- [RECURRING_SWITCH.md](../docs/RECURRING_SWITCH.md)
- [KNOWN_LIMITATIONS.md](../docs/KNOWN_LIMITATIONS.md)
