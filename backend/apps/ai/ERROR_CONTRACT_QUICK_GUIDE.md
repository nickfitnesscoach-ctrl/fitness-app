# Error Contract — Шпаргалка для разработчиков

**Простым языком:** Единый формат ответа для всех ошибок AI-обработки фотографий.

---

## Зачем это нужно?

**Было (плохо):**
```json
{"error": "timeout"}  // Что делать? Где trace_id?
```

**Стало (хорошо):**
```json
{
  "error_code": "AI_TIMEOUT",
  "user_title": "Не получилось обработать фото",
  "user_message": "Сервер не ответил вовремя. Попробуйте ещё раз.",
  "user_actions": ["retry"],
  "allow_retry": true,
  "retry_after_sec": 30,
  "trace_id": "abc123"
}
```

**Профит:**
- ✅ Фронтенд знает, что показать пользователю (`user_title`, `user_message`)
- ✅ Фронтенд знает, какие кнопки показать (`user_actions`)
- ✅ Поддержка может найти ошибку в логах (`trace_id`)
- ✅ Единый формат для всех ошибок (проще тестировать)

---

## Обязательные поля

| Поле | Описание | Пример |
|------|----------|--------|
| `error_code` | Уникальный код (UPPERCASE) | `"AI_TIMEOUT"` |
| `user_title` | Короткий заголовок | `"Не получилось обработать фото"` |
| `user_message` | Подробное объяснение | `"Сервер не ответил вовремя..."` |
| `user_actions` | Что может сделать пользователь | `["retry", "contact_support"]` |
| `allow_retry` | Можно ли повторить | `true` или `false` |
| `trace_id` | ID для поиска в логах | `"65809ff15532..."` |

### Опциональные поля

- `retry_after_sec` — Сколько секунд ждать перед retry (для RATE_LIMIT, AI_TIMEOUT)
- `debug_details` — Технические детали (только в DEBUG режиме)

---

## Как использовать?

### 1. В views.py — вернуть ошибку

```python
from apps.ai.error_contract import AIErrorRegistry

# Генерируем trace_id
request_id = uuid.uuid4().hex

# Выбираем нужную ошибку из реестра
error_def = AIErrorRegistry.INVALID_IMAGE

# Возвращаем ответ
response = Response(
    error_def.to_dict(trace_id=request_id),
    status=status.HTTP_400_BAD_REQUEST
)
response['X-Request-ID'] = request_id
return response
```

### 2. В tasks.py — вернуть ошибку из Celery

```python
from apps.ai.error_contract import AIErrorRegistry

def _error_response(error_def, meal_id, meal_photo_id, user_id, trace_id):
    return {
        **error_def.to_dict(trace_id=trace_id),  # Все поля Error Contract
        "items": [],
        "totals": {},
        "meal_id": meal_id,
        "meal_photo_id": meal_photo_id,
        "owner_id": user_id,
    }

# Использование
result = _error_response(
    AIErrorRegistry.AI_TIMEOUT,
    meal_id=123,
    meal_photo_id=456,
    user_id=789,
    trace_id=request_id
)
```

### 3. Exception handler — автоматическая обработка

Throttling (RATE_LIMIT) и ValidationError (INVALID_IMAGE) обрабатываются автоматически в `exception_handler.py`.

**Не нужно ничего делать**, просто поднять `rest_framework.exceptions.Throttled` или `ValidationError`.

---

## Список всех error_code

### Timeout ошибки
- `AI_TIMEOUT` — сервер не ответил вовремя
- `UPSTREAM_TIMEOUT` — AI-сервис не ответил

### Server ошибки
- `AI_SERVER_ERROR` — сервер временно недоступен
- `UPSTREAM_ERROR` — AI-сервис недоступен
- `INTERNAL_ERROR` — внутренняя ошибка

### Validation ошибки
- `INVALID_IMAGE` — файл повреждён или не является изображением
- `UNSUPPORTED_IMAGE_FORMAT` — неподдерживаемый формат
- `IMAGE_TOO_LARGE` — фото слишком большое
- `IMAGE_DECODE_FAILED` — не удалось декодировать
- `EMPTY_RESULT` — AI не распознал еду
- `UNSUPPORTED_CONTENT` — на фото нет еды

### Limit ошибки
- `DAILY_PHOTO_LIMIT_EXCEEDED` — дневной лимит исчерпан
- `RATE_LIMIT` — слишком много запросов

### Системные ошибки
- `CANCELLED` — обработка отменена
- `PHOTO_NOT_FOUND` — фото не найдено
- `INVALID_STATUS` — недопустимое состояние для retry

---

## user_actions — что это?

**Варианты действий:**

| Action | Когда использовать | Пример |
|--------|-------------------|--------|
| `"retry"` | Временная ошибка, можно повторить | AI_TIMEOUT, RATE_LIMIT |
| `"retake"` | Проблема с фото, нужно новое | INVALID_IMAGE, BLURRY |
| `"upgrade"` | Лимит исчерпан, нужна подписка | DAILY_PHOTO_LIMIT_EXCEEDED |
| `"contact_support"` | Непонятная ошибка, нужна помощь | INTERNAL_ERROR, INVALID_STATUS |

**Фронтенд показывает соответствующие кнопки:**
- `["retry"]` → кнопка "Попробовать ещё раз"
- `["retake"]` → кнопка "Сделать новое фото"
- `["upgrade"]` → кнопка "Оформить PRO"
- `["contact_support"]` → кнопка "Написать в поддержку"

---

## Как добавить новый error_code?

### Шаг 1: Добавить в AIErrorRegistry

**Файл:** `backend/apps/ai/error_contract.py`

```python
class AIErrorRegistry:
    # ... existing errors ...

    MY_NEW_ERROR = AIErrorDefinition(
        code="MY_NEW_ERROR",
        user_title="Короткий заголовок (1-5 слов)",
        user_message="Подробное объяснение для пользователя (1-2 предложения).",
        user_actions=["retry"],  # или ["retake", "contact_support", "upgrade"]
        allow_retry=True,  # или False
        retry_after_sec=60,  # опционально
        category="validation",  # или "timeout", "server", "limit", "unknown"
    )
```

### Шаг 2: Использовать в коде

```python
from apps.ai.error_contract import AIErrorRegistry

error_def = AIErrorRegistry.MY_NEW_ERROR
return Response(
    error_def.to_dict(trace_id=request_id),
    status=status.HTTP_400_BAD_REQUEST
)
```

### Шаг 3: Написать тест

```python
def test_my_new_error():
    response = self.client.post(url, data={})

    assert response.status_code == 400
    body = response.json()

    # Проверить все поля Error Contract
    assert body["error_code"] == "MY_NEW_ERROR"
    assert "trace_id" in body
    assert body["allow_retry"] is True
    assert "user_title" in body
    assert "user_message" in body
    assert "user_actions" in body
```

---

## FAQ

### В чём разница между `allow_retry` и `user_actions`?

- **`allow_retry`** — техническая возможность (true/false)
- **`user_actions`** — что показать пользователю

**Пример:**
```python
# RATE_LIMIT
allow_retry=True  # Можно повторить
user_actions=["retry"]  # Показать кнопку "Попробовать ещё раз"

# INVALID_IMAGE
allow_retry=False  # Повторять бесполезно (файл битый)
user_actions=["retake"]  # Показать кнопку "Сделать новое фото"
```

### Зачем нужен trace_id?

**Для поиска в логах.**

**Сценарий:**
1. Пользователь получил ошибку с `trace_id: "abc123"`
2. Пишет в поддержку: "Ошибка abc123"
3. Админ ищет: `docker logs backend | grep "abc123"`
4. Видит полный стек-трейс и контекст

### Когда `retry_after_sec` обязателен?

**Обязателен для:**
- `RATE_LIMIT` — показать, сколько секунд ждать
- Timeout ошибки (`AI_TIMEOUT`, `UPSTREAM_TIMEOUT`)

**Необязателен для:**
- Validation ошибки (`INVALID_IMAGE`) — retry бесполезен
- Limit ошибки (`DAILY_PHOTO_LIMIT_EXCEEDED`) — retry до конца дня бесполезен

---

## Примеры реальных ответов

### RATE_LIMIT (429)
```json
{
  "error_code": "RATE_LIMIT",
  "user_title": "Слишком много запросов",
  "user_message": "Подождите немного перед следующей попыткой.",
  "user_actions": ["retry"],
  "allow_retry": true,
  "retry_after_sec": 38,
  "trace_id": "65809ff1553243309da6a456dd24de5d"
}
```

**HTTP заголовок:** `Retry-After: 38`

---

### INVALID_IMAGE (400)
```json
{
  "error_code": "INVALID_IMAGE",
  "user_title": "Не удалось обработать фото",
  "user_message": "Файл повреждён или не является изображением.",
  "user_actions": ["retake"],
  "allow_retry": false,
  "trace_id": "4dcaad938c354e2eb397a4b4229abefc"
}
```

---

### DAILY_PHOTO_LIMIT_EXCEEDED (429)
```json
{
  "error_code": "DAILY_PHOTO_LIMIT_EXCEEDED",
  "user_title": "Дневной лимит исчерпан",
  "user_message": "Вы исчерпали дневной лимит фото. Оформите PRO для безлимита.",
  "user_actions": ["upgrade"],
  "allow_retry": false,
  "trace_id": "abc123"
}
```

---

### INVALID_STATUS (400)
```json
{
  "error_code": "INVALID_STATUS",
  "user_title": "Недопустимое состояние",
  "user_message": "Можно повторить только неудавшиеся фото.",
  "user_actions": ["contact_support"],
  "allow_retry": false,
  "trace_id": "xyz789"
}
```

---

## Тестирование

### Автотесты (pytest)

```bash
cd backend

# Все AI тесты с Error Contract валидацией
pytest apps/ai/tests/test_invalid_status.py -v
pytest apps/ai/tests/test_async_flow.py::TestAIAsyncFlow::test_limit_exceeded_returns_429_no_meal_created -v
```

### Ручные тесты (локально)

**RATE_LIMIT:**
```bash
python test_throttle.py
# Ожидаем: 15 запросов → последние 5 вернут 429 + RATE_LIMIT
```

**INVALID_IMAGE:**
```bash
python test_invalid_image.py
# Ожидаем: 400 + INVALID_IMAGE + trace_id
```

---

## Проверка в production

```bash
# Пример: PHOTO_NOT_FOUND
curl -X POST https://eatfit24.ru/api/v1/ai/recognize/ \
  -F "meal_photo_id=999999" \
  -F "image=@test.jpg" \
  -F "meal_type=BREAKFAST" \
  -F "date=2026-01-16"

# Ожидаем:
# HTTP 404
# {"error_code": "PHOTO_NOT_FOUND", "trace_id": "...", ...}
```

---

## Ссылки

- **Полная документация:** [ERROR_CONTRACT_VALIDATION_REPORT.md](../../../ERROR_CONTRACT_VALIDATION_REPORT.md)
- **Код реестра:** [error_contract.py](error_contract.py)
- **Exception handler:** [backend/apps/core/exception_handler.py](../../core/exception_handler.py)
- **Тесты:** [tests/](tests/)

---

**Последнее обновление:** 2026-01-16
**Статус:** ✅ Production-ready
