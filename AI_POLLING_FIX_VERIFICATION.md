# AI Polling Fix - Verification Guide

## Исправленные проблемы (P0)

### 1. Терминальные статусы (P0) ✅
**Было:** `status.state === 'SUCCESS' && status.status === 'success'` (AND-логика)
**Стало:** `status.state === 'SUCCESS' || status.status === 'success'` (OR-логика)

**Почему:** Бэкенд может возвращать только одно из полей, и поллинг зависал в бесконечном цикле.

### 2. Timeout увеличен (P0) ✅
**Было:** 60 секунд
**Стало:** 120 секунд

**Почему:** AI-задачи могут занимать до 90 секунд на бэкенде, 60 секунд было слишком мало.

### 3. Max attempts guard (P0) ✅
Добавлена защита от бесконечного поллинга:
- Если сервер никогда не вернёт терминальный статус, поллинг остановится после `maxAttempts`
- `maxAttempts = CLIENT_TIMEOUT_MS / FAST_PHASE_DELAY_MS` (~120 попыток за 120 секунд)

### 4. Детальное логирование (P0) ✅
Все логи теперь с префиксом `[AI]`:
- `Task ${taskId} status: state=XXX, status=YYY` — каждый опрос статуса
- `Task ${taskId} SUCCESS` — при успешном завершении
- `Task ${taskId} FAILED` — при ошибке
- `Task ${taskId} still processing (attempt X/Y, elapsed Zms)` — прогресс

---

## Как проверить фикс (5 минут)

### Шаг 1: Откройте Network в DevTools

1. Откройте Chrome DevTools (F12)
2. Перейдите на вкладку **Network**
3. Включите фильтр: `task-status` или `/api/v1/ai/task/`

### Шаг 2: Загрузите фото

1. Откройте `/food-log` в приложении
2. Выберите любое фото еды
3. Нажмите "Анализировать"

### Шаг 3: Смотрите Network

**Что должно быть:**

1. **Запрос на загрузку фото** (POST `/api/v1/ai/recognize/`):
   ```json
   Response 202:
   {
     "task_id": "abc-123-def-456",
     "meal_id": 42,
     "meal_photo_id": 17,
     "status": "processing"
   }
   ```

2. **Поллинг статуса задачи** (GET `/api/v1/ai/task/<task_id>/`):
   - Первые 15 секунд: запросы каждую **1 секунду**
   - После 15 секунд: запросы каждые **3-5 секунд** (с backoff)
   - Максимум **120 секунд** (или ~120 попыток)

3. **Терминальный статус (SUCCESS)**:
   ```json
   {
     "task_id": "abc-123-def-456",
     "state": "SUCCESS",        // Celery state
     "status": "success",        // Backend status
     "result": {
       "meal_id": 42,
       "items": [...]
     }
   }
   ```

4. **Терминальный статус (FAILURE)**:
   ```json
   {
     "task_id": "abc-123-def-456",
     "state": "FAILURE",         // Celery state
     "status": "failed",         // Backend status
     "error": "UPSTREAM_TIMEOUT",
     "result": {
       "error_message": "Сервер распознавания не ответил вовремя"
     }
   }
   ```

### Шаг 4: Проверьте Console логи

Откройте Console в DevTools и найдите логи с префиксом `[AI]`:

**Нормальный flow:**
```
[API] AI recognize: 2.jpg
[API] X-Request-ID: req_abc123
[API] Get task status: abc-123-def-456
[API] Task abc-123-def-456 status: state=PENDING, status=processing
[AI] Task abc-123-def-456 still processing (attempt 1/120, elapsed 1000ms)
[API] Get task status: abc-123-def-456
[API] Task abc-123-def-456 status: state=STARTED, status=processing
[AI] Task abc-123-def-456 still processing (attempt 2/120, elapsed 2000ms)
...
[API] Get task status: abc-123-def-456
[API] Task abc-123-def-456 status: state=SUCCESS, status=success
[AI] Task abc-123-def-456 SUCCESS - mapping result
[AI] Task abc-123-def-456 mapped successfully: { meal_id: 42, recognized_items: [...] }
```

**Flow с ошибкой:**
```
[API] AI recognize: 2.jpg
[API] Get task status: abc-123-def-456
[API] Task abc-123-def-456 status: state=FAILURE, status=failed
[AI] Task abc-123-def-456 FAILED: UPSTREAM_TIMEOUT
```

**Flow с timeout (новый guard):**
```
[AI] Task abc-123-def-456 still processing (attempt 120/120, elapsed 120000ms)
Error: Слишком много попыток проверки статуса
```

---

## Definition of Done (DoD)

Фикс считается завершённым, когда:

1. ✅ **Поллинг доходит до SUCCESS/FAILED и останавливается**
   - Проверить: В Network нет бесконечных запросов `task-status`
   - В Console есть лог `[AI] Task XXX SUCCESS` или `FAILED`

2. ✅ **FAILED корректно отображается в UI**
   - Проверить: Фото показывает красную плашку "Ошибка" с текстом ошибки
   - Кнопка "Повторить" активна (если ошибка retryable)

3. ✅ **Timeout работает (120 секунд)**
   - Проверить: Если задача зависла, через 120 секунд показывается "Слишком долго обрабатываем"

4. ✅ **New Upload → новый Meal**
   - Проверить: После "Закрыть" и нового загрузки создаётся **новый meal_id** (не перетирается старый)

5. ✅ **Retry → новый MealPhoto в том же Meal**
   - Проверить: При retry на failed фото создаётся новый task_id, но meal_id сохраняется

---

## Быстрый способ проверить (1 минута)

1. Откройте DevTools → Network → включите фильтр `task-status`
2. Загрузите фото
3. Посмотрите **последний запрос** `task-status`:
   - **Если Response содержит `"state": "SUCCESS"` или `"status": "success"`** — поллинг должен остановиться
   - **Если запросы продолжаются после терминального статуса** — фикс не сработал

4. Проверьте Console:
   - Должен быть лог `[AI] Task XXX SUCCESS - mapping result` ИЛИ `[AI] Task XXX FAILED`
   - Если есть `still processing` после терминального статуса — фикс не сработал

---

## Что делать, если фикс не работает

### Проблема: Бесконечный поллинг после SUCCESS

**Причина:** Бэкенд возвращает нестандартные значения `state`/`status`.

**Решение:**
1. Откройте DevTools → Network → найдите последний запрос `task-status`
2. Скопируйте Response JSON
3. Проверьте:
   - Какие значения в `state` и `status`?
   - Есть ли поле `result`?
4. Добавьте эти значения в проверку терминальных статусов

### Проблема: Timeout не работает (вечная обработка)

**Причина:** `CLIENT_TIMEOUT_MS` не применяется из-за кеширования модуля.

**Решение:**
1. Остановите dev-сервер
2. Удалите `node_modules/.vite`
3. Перезапустите `npm run dev`

### Проблема: 401 Unauthorized при поллинге

**Причина:** Токен протух или не обновляется.

**Решение:** Уже исправлено в предыдущем фиксе (добавлено auto-refresh токена в `fetchWithTimeout`).

---

## Технические детали

### Файлы изменены:

1. **frontend/src/features/ai/hooks/useFoodBatchAnalysis.ts**
   - Строки 111-169: Изменена логика `pollTask()`
   - OR-логика для терминальных статусов
   - Добавлен `maxAttempts` guard
   - Детальное логирование

2. **frontend/src/features/ai/model/constants.ts**
   - Строка 30: `CLIENT_TIMEOUT_MS: 120000` (было 60000)

3. **frontend/src/features/ai/api/ai.api.ts**
   - Строки 140-143: Добавлено логирование `state` и `status` в `getTaskStatus()`

### Конфигурация поллинга:

```typescript
POLLING_CONFIG = {
  FAST_PHASE_DURATION_MS: 15000,      // Первые 15 секунд
  FAST_PHASE_DELAY_MS: 1000,          // Каждую 1 секунду
  SLOW_PHASE_DELAY_MS: 3000,          // После 15 секунд — каждые 3 секунды
  SLOW_PHASE_MAX_DELAY_MS: 5000,      // Максимум 5 секунд между запросами
  BACKOFF_MULTIPLIER: 1.3,            // Экспоненциальный backoff
  CLIENT_TIMEOUT_MS: 120000,          // Жёсткий лимит 120 секунд
}
```

### Терминальные статусы (SSOT):

```typescript
// SUCCESS: останов поллинга
isSuccess = status.state === 'SUCCESS' || status.status === 'success'

// FAILURE: останов поллинга
isFailure = status.state === 'FAILURE' || status.status === 'failed'

// PROCESSING: продолжить поллинг
isPending = !isSuccess && !isFailure
// (PENDING, STARTED, RETRY)
```
