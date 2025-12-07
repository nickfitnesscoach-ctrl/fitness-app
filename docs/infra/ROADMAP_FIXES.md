# EatFit24 - Полный Аудит и Roadmap Исправлений

**Дата аудита:** 2025-12-06  
**Последнее обновление:** 2025-12-07  
**Версия:** 1.1  
**Аудитор:** Droid (AI Agent)

---

## Содержание

1. [Резюме аудита](#резюме-аудита)
2. [Фаза 0: Найденные проблемы](#фаза-0-найденные-проблемы)
3. [Фаза 1: Критические фиксы (P0)](#фаза-1-критические-фиксы-p0)
4. [Фаза 2: Нормализация архитектуры (P1)](#фаза-2-нормализация-архитектуры-p1)
5. [Фаза 3: UX-финализация (P2)](#фаза-3-ux-финализация-p2)
6. [Фаза 4: Оптимизация производительности](#фаза-4-оптимизация-производительности)
7. [Фаза 5: Тестирование](#фаза-5-тестирование)
8. [Фаза 6: Документация](#фаза-6-документация)

---

## Резюме аудита

### Статистика

| Компонент | Критические (P0) | Высокие (P1) | Средние (P2) | Низкие (P3) |
|-----------|------------------|--------------|--------------|-------------|
| Frontend  | 3                | 12           | 18           | 8           |
| Backend   | 2                | 8            | 11           | 5           |
| AI-Proxy  | 1                | 4            | 6            | 3           |
| DevOps    | 2                | 5            | 4            | 2           |
| **Итого** | **8**            | **29**       | **39**       | **18**      |

### Главная проблема (РЕШЕНА)
**BUG-001: "Еда не найдена" при успешном распознавании** - ИСПРАВЛЕНО 2025-12-06

### Прогресс исправлений (2025-12-07)
| Фаза | Статус | Выполнено |
|------|--------|-----------|
| Фаза 1 (P0) | ✅ ЗАВЕРШЕНА | 6/6 задач |
| Фаза 2 (P1) | ✅ ЗАВЕРШЕНА | 8/8 задач |
| Фаза 3 (P2) | ✅ ЗАВЕРШЕНА | 6/6 задач |
| Фаза 4 (Perf) | ✅ ЗАВЕРШЕНА | 5/5 задач |
| Фаза 5 (Tests) | ✅ ЗАВЕРШЕНА | Unit + Integration tests |
| Фаза 6 | ⏳ В очереди | Документация |

---

## Фаза 0: Найденные проблемы

### 0.1 FRONTEND - Критические проблемы (P0)

#### F-001: [ИСПРАВЛЕНО] Ложная ошибка "Еда не найдена"
- **Severity:** P0 BLOCKER
- **Файлы:** `FoodLogPage.tsx`, `BatchResultsModal.tsx`, `constants/index.ts`
- **Описание:** UI показывал красную ошибку при успешном создании meal
- **Статус:** ИСПРАВЛЕНО (commit d1efd6b)

#### F-002: Несогласованность типов ID между слоями
- **Severity:** P0
- **Файлы:** `types.ts`, `ai.ts`, `nutrition.ts`
- **Описание:** Backend возвращает `id: number`, Celery task возвращает `id: string`, frontend ожидает оба варианта
- **Детали:**
  ```typescript
  // Frontend types.ts - ожидает number
  interface FoodItem { id: number; ... }
  
  // Backend tasks.py - возвращает string
  'id': str(food_item.id)
  
  // Backend serializers - возвращает number
  'id': item.id
  ```
- **Риск:** Ошибки сравнения и поиска элементов
- **Решение:** Унифицировать на `number` или везде использовать `String(id)`

#### F-003: Отсутствие iframe CSP заголовков для Telegram Web
- **Severity:** P0
- **Файлы:** `nginx-eatfit24.ru.conf`
- **Описание:** Telegram Web может блокировать Mini App в iframe без правильных заголовков
- **Недостающие заголовки:**
  ```nginx
  add_header X-Frame-Options "ALLOW-FROM https://web.telegram.org";
  add_header Content-Security-Policy "frame-ancestors 'self' https://web.telegram.org https://*.telegram.org";
  ```

### 0.2 FRONTEND - Высокие проблемы (P1)

#### F-004: Несогласованность полей между API слоями
- **Severity:** P1
- **Описание:** Разные имена полей в разных местах
- **Примеры:**
  | Место | Поле веса | Поле углеводов |
  |-------|-----------|----------------|
  | AI Proxy Response | `grams` | `carbs` |
  | Backend Task | `grams` | `carbohydrates` |
  | Frontend Types | `grams` | `carbohydrates` |
  | AI Proxy Schema | `grams` | `carbs` |
  | Backend Adapter | `estimated_weight` | `carbohydrates` |

#### F-005: MealDetailsPage использует несуществующее поле `amount_grams`
- **Severity:** P1
- **Файл:** `pages/MealDetailsPage.tsx`, строка 109
- **Код:**
  ```typescript
  setItemToEdit({ id: item.id, name: item.name, grams: item.amount_grams });
  // Backend возвращает item.grams, не item.amount_grams
  ```
- **Последствие:** Edit modal показывает undefined вместо веса

#### F-006: updateFoodItem отправляет `amount_grams` вместо `grams`
- **Severity:** P1
- **Файл:** `services/api/nutrition.ts`, строка 95
- **Код:**
  ```typescript
  data: { name?: string; amount_grams?: number }
  // Backend ожидает { name?: string; grams?: number }
  ```

#### F-007: Отсутствует обработка HEIC формата на фронте
- **Severity:** P1
- **Описание:** iOS делает фото в HEIC, но frontend не конвертирует его
- **Файл:** `FoodLogPage.tsx`
- **Решение:** Использовать `heic2any` библиотеку

#### F-008: Нет retry логики для polling
- **Severity:** P1
- **Файл:** `FoodLogPage.tsx`, `pollTaskStatus`
- **Описание:** При сетевой ошибке polling останавливается после 3 попыток

#### F-009: BillingContext не обрабатывает race condition при refresh
- **Severity:** P1
- **Файл:** `contexts/BillingContext.tsx`

#### F-010: AuthContext не восстанавливается после ошибки backend
- **Severity:** P1
- **Файл:** `contexts/AuthContext.tsx`

#### F-011: Отсутствует валидация размера фото на frontend
- **Severity:** P1
- **Файл:** `FoodLogPage.tsx`

#### F-012: Calendar компонент не локализован
- **Severity:** P1
- **Файл:** `components/Calendar.tsx`

#### F-013: Нет offline режима / кэширования
- **Severity:** P1

#### F-014: Telegram theme не применяется к scrollbar
- **Severity:** P1

#### F-015: useTelegramWebApp delay 100ms может быть недостаточным
- **Severity:** P1
- **Файл:** `hooks/useTelegramWebApp.ts`, строка 91

### 0.3 FRONTEND - Средние проблемы (P2)

#### F-016: Дублирование логики fallback в pollTaskStatus и processBatch
- **Severity:** P2
- **Файл:** `FoodLogPage.tsx`

#### F-017: console.log в production коде
- **Severity:** P2

#### F-018: Отсутствует error boundary для отдельных компонентов
- **Severity:** P2

#### F-019: Нет skeleton loaders
- **Severity:** P2

#### F-020: MacroChart не адаптируется к темной теме Telegram
- **Severity:** P2

#### F-021: ProfileEditModal не валидирует данные до отправки
- **Severity:** P2

#### F-022: Нет debounce для частых действий
- **Severity:** P2

#### F-023: Avatar компонент не обрабатывает ошибку загрузки
- **Severity:** P2

#### F-024: Hardcoded цвета вместо CSS variables
- **Severity:** P2

#### F-025: Нет поддержки landscape orientation
- **Severity:** P2

#### F-026: Нет анимации при переходах между страницами
- **Severity:** P2

#### F-027: Subscription page не показывает loading при покупке
- **Severity:** P2

#### F-028: Settings page не обновляется после изменений
- **Severity:** P2

#### F-029: Нет toast notifications
- **Severity:** P2

#### F-030: PaymentHistory не пагинируется на frontend
- **Severity:** P2

#### F-031: InviteClientPage URL не копируется на мобильных
- **Severity:** P2

#### F-032: FoodLogPage не запоминает последний выбранный meal_type
- **Severity:** P2

#### F-033: Отсутствует pull-to-refresh
- **Severity:** P2

### 0.4 BACKEND - Критические проблемы (P0)

#### B-001: Celery task удаляет meal при пустых items
- **Severity:** P0
- **Файл:** `apps/ai/tasks.py`, строки 112-118
- **Код:**
  ```python
  if recognized_items:
      # ... create items
  else:
      error_msg = result.get('error', 'No food items recognized')
      meal.delete()  # <-- ПРОБЛЕМА
  ```
- **Описание:** При пустом ответе AI удаляется meal, хотя он уже мог быть показан пользователю
- **Риск:** Пользователь видит meal в дневнике, а затем он исчезает

#### B-002: Race condition при создании DailyUsage
- **Severity:** P0
- **Файл:** `apps/billing/usage.py`

### 0.5 BACKEND - Высокие проблемы (P1)

#### B-003: AI Proxy adapter теряет confidence
- **Severity:** P1
- **Файл:** `apps/ai_proxy/adapter.py`, строка 52

#### B-004: Нет rate limiting на /ai/task/{id}/
- **Severity:** P1
- **Файл:** `apps/ai/views.py`, TaskStatusView

#### B-005: Отсутствует cleanup для stale Celery tasks
- **Severity:** P1

#### B-006: Нет мониторинга Celery queue length
- **Severity:** P1

#### B-007: FoodItem serializer использует кириллицу в validation messages
- **Severity:** P1
- **Файл:** `apps/nutrition/serializers.py`
- **Сообщения отображаются как мусор из-за неправильной кодировки

#### B-008: Нет graceful shutdown для Celery worker
- **Severity:** P1
- **Файл:** `docker-compose.yml`

#### B-009: Subscription expires_at timezone не учитывается
- **Severity:** P1

#### B-010: Нет retry для YooKassa webhook failures
- **Severity:** P1

### 0.6 BACKEND - Средние проблемы (P2)

#### B-011: N+1 query в getMeals
- **Severity:** P2

#### B-012: Отсутствует индекс на (user_id, date) для Meal
- **Severity:** P2

#### B-013: Нет сжатия изображений при upload
- **Severity:** P2

#### B-014: DailyGoal history не ограничена
- **Severity:** P2

#### B-015: Отсутствует audit log для billing операций
- **Severity:** P2

#### B-016: Нет health check для AI Proxy connection
- **Severity:** P2

#### B-017: Telegram authentication не кэширует результат
- **Severity:** P2

#### B-018: Отсутствует cleanup для expired sessions
- **Severity:** P2

#### B-019: Нет метрик для AI recognition latency
- **Severity:** P2

#### B-020: Management commands не имеют logging
- **Severity:** P2

#### B-021: Test coverage < 50%
- **Severity:** P2

### 0.7 AI-PROXY - Критические проблемы (P0)

#### A-001: Нет timeout для OpenRouter API call
- **Severity:** P0
- **Файл:** `eatfit24-ai-proxy/app/openrouter_client.py`, строка 105
- **60 секунд - слишком много, пользователь уйдет**

### 0.8 AI-PROXY - Высокие проблемы (P1)

#### A-002: Нет retry для OpenRouter API
- **Severity:** P1

#### A-003: API key хранится в памяти
- **Severity:** P1

#### A-004: Нет validation для output JSON
- **Severity:** P1

#### A-005: Health endpoint не проверяет OpenRouter connection
- **Severity:** P1

### 0.9 AI-PROXY - Средние проблемы (P2)

#### A-006: Нет кэширования для одинаковых изображений
- **Severity:** P2

#### A-007: Prompt не параметризован
- **Severity:** P2

#### A-008: Нет fallback на другую модель
- **Severity:** P2

#### A-009: Логи не структурированы (не JSON)
- **Severity:** P2

#### A-010: Нет метрик (Prometheus/StatsD)
- **Severity:** P2

#### A-011: Отсутствует rate limiting per API key
- **Severity:** P2

### 0.10 DEVOPS - Критические проблемы (P0)

#### D-001: Nginx не имеет iframe headers для Telegram
- **Severity:** P0
- **Файл:** `deploy/nginx-eatfit24.ru.conf`

#### D-002: Redis не имеет persistence конфигурации
- **Severity:** P0
- **`allkeys-lru` может удалить результаты незавершенных задач**

### 0.11 DEVOPS - Высокие проблемы (P1)

#### D-003: Нет log rotation
- **Severity:** P1

#### D-004: Celery worker concurrency=4 может быть мало
- **Severity:** P1

#### D-005: Нет backup стратегии для PostgreSQL
- **Severity:** P1

#### D-006: Отсутствует monitoring (Grafana/Prometheus)
- **Severity:** P1

#### D-007: SSL certificates не auto-renew
- **Severity:** P1

### 0.12 DEVOPS - Средние проблемы (P2)

#### D-008: Нет resource limits для контейнеров
- **Severity:** P2

#### D-009: AI Proxy не в docker-compose
- **Severity:** P2

#### D-010: Нет healthcheck для bot контейнера
- **Severity:** P2

#### D-011: Отсутствует staging environment
- **Severity:** P2

---

## Фаза 1: Критические фиксы (P0)

### 1.1 [DONE] Исправление "Еда не найдена" (F-001)
- **Статус:** ИСПРАВЛЕНО
- **Commit:** d1efd6b

### 1.2 Унификация типов ID (F-002)
- **Приоритет:** P0
- **Время:** 2 часа
- **Файлы:**
  - `backend/apps/ai/tasks.py` - изменить `str(food_item.id)` на `food_item.id`
  - `frontend/src/services/api/ai.ts` - добавить type guard

### 1.3 Nginx iframe headers (D-001)
- **Приоритет:** P0
- **Время:** 30 минут
- **Файл:** `deploy/nginx-eatfit24.ru.conf`
- **Добавить:**
  ```nginx
  add_header X-Frame-Options "ALLOW-FROM https://web.telegram.org" always;
  add_header Content-Security-Policy "frame-ancestors 'self' https://web.telegram.org https://*.telegram.org" always;
  ```

### 1.4 Celery task не должен удалять meal (B-001)
- **Приоритет:** P0
- **Время:** 1 час
- **Файл:** `backend/apps/ai/tasks.py`

### 1.5 Redis persistence fix (D-002)
- **Приоритет:** P0
- **Время:** 30 минут
- **Файл:** `docker-compose.yml`
- **Изменить:** `allkeys-lru` на `volatile-lru`

### 1.6 OpenRouter timeout reduction (A-001)
- **Приоритет:** P0
- **Время:** 30 минут
- **Изменить:** `timeout=60.0` на `timeout=30.0`

---

## Фаза 2: Нормализация архитектуры (P1)

### 2.1 Унификация полей API (F-004)
- **Время:** 4 часа
- AI Proxy: `carbs` на `carbohydrates`

### 2.2 Fix MealDetailsPage amount_grams (F-005, F-006)
- **Время:** 1 час

### 2.3 HEIC support (F-007)
- **Время:** 2 часа

### 2.4 Celery rate limiting (B-004)
- **Время:** 1 час

### 2.5 Fix encoding in serializers (B-007)
- **Время:** 30 минут

### 2.6 Graceful shutdown для Celery (B-008)
- **Время:** 1 час

### 2.7 OpenRouter retry logic (A-002)
- **Время:** 2 часа

### 2.8 Health check improvements (A-005)
- **Время:** 1 час

---

## Фаза 3: UX-финализация (P2)

### 3.1 Skeleton loaders (F-019)
- **Время:** 3 часа

### 3.2 Toast notifications (F-029)
- **Время:** 2 часа

### 3.3 Dark mode support (F-020)
- **Время:** 4 часа

### 3.4 Debounce для кнопок (F-022)
- **Время:** 1 час

### 3.5 Pull-to-refresh (F-033)
- **Время:** 2 часа

### 3.6 Offline indicator (F-013)
- **Время:** 2 часа

---

## Фаза 4: Оптимизация производительности

### 4.1 N+1 queries fix (B-011)
- **Время:** 2 часа

### 4.2 Image compression (B-013)
- **Время:** 3 часа

### 4.3 Query optimization indexes (B-012)
- **Время:** 1 час

### 4.4 Frontend bundle optimization
- **Время:** 2 часа

### 4.5 API response caching
- **Время:** 3 часа

---

## Фаза 5: Тестирование

### 5.1 Unit tests для Frontend
- **Время:** 8 часов
- **Coverage target:** 70%

### 5.2 Integration tests для Backend
- **Время:** 8 часов
- **Coverage target:** 80%

### 5.3 E2E tests
- **Время:** 8 часов
- **Инструмент:** Playwright

### 5.4 Load testing
- **Время:** 4 часа
- **Инструмент:** k6

---

## Фаза 6: Документация

### 6.1 API Documentation
- **Время:** 4 часа

### 6.2 Developer README
- **Время:** 2 часа

### 6.3 Deployment Guide
- **Время:** 2 часа

### 6.4 Debug Mode Guide
- **Время:** 1 час

---

## Приоритезация и Timeline

### Неделя 1 (Критические)
| День | Задача | Время |
|------|--------|-------|
| 1 | 1.2 Унификация ID | 2ч |
| 1 | 1.3 Nginx headers | 30м |
| 1 | 1.4 Celery meal deletion | 1ч |
| 1 | 1.5 Redis persistence | 30м |
| 2 | 1.6 OpenRouter timeout | 30м |
| 2 | 2.1 API fields унификация | 4ч |
| 3 | 2.2 MealDetailsPage fix | 1ч |
| 3 | 2.3 HEIC support | 2ч |
| 4 | 2.4 Rate limiting | 1ч |
| 4 | 2.5 Encoding fix | 30м |
| 5 | 2.6 Graceful shutdown | 1ч |
| 5 | 2.7 OpenRouter retry | 2ч |

### Неделя 2 (UX + Performance)
- Фаза 3: UX improvements (3.1-3.6)
- Фаза 4: Performance (4.1-4.3)

### Неделя 3 (Testing + Docs)
- Фаза 5: Testing (5.1-5.4)
- Фаза 6: Documentation (6.1-6.4)

---

## Риски и Зависимости

### Риски
1. **OpenRouter API изменения** - нужен мониторинг их changelog
2. **Telegram WebApp API изменения** - следить за updates
3. **YooKassa webhook reliability** - нужен fallback механизм

### Зависимости
- F-007 (HEIC) требует тестирования на iOS
- D-001 (iframe) требует тестирования в Telegram Web
- B-001 требует согласования с product owner

---

## Заключение

Аудит выявил **94 проблемы** различной severity:
- 8 критических (P0) - требуют немедленного исправления
- 29 высоких (P1) - исправить в течение недели
- 39 средних (P2) - исправить в течение 2-3 недель
- 18 низких (P3) - backlog

**Главная проблема "Еда не найдена" ИСПРАВЛЕНА.**

Оставшиеся P0 проблемы должны быть исправлены в течение 2-3 дней для стабильной работы production.

