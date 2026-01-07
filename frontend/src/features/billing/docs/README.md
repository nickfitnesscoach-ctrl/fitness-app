# Billing Feature Module

> **Модуль биллинга EatFit24** — изолированный домен для управления подписками, платежами и лимитами.

---

## Назначение

Этот Feature-модуль содержит всё, что связано с:

- Отображением и выбором тарифных планов (FREE/PRO_MONTHLY/PRO_YEARLY)
- Управлением подпиской (автопродление, привязка карты)
- Историей платежей
- Daily limits для фото-распознавания

---

## Точки входа (Routes)

| Роут | Страница | Назначение |
|------|----------|------------|
| `/subscription` | `SubscriptionPage` | Выбор и покупка тарифа |
| `/settings/subscription` | `SubscriptionDetailsPage` | Управление подпиской |
| `/settings/history` | `PaymentHistoryPage` | История платежей |

---

## Архитектура состояния

```
BillingContext (глобальный)
├── subscription: SubscriptionDetails
├── billingMe: BillingMe (лимиты)
├── isPro: boolean
├── isLimitReached: boolean
└── методы: refresh(), setAutoRenew(), addPaymentMethod()
```

**Источник истины** для биллинга — `BillingContext`, который загружает данные из:
- `GET /billing/me/` — лимиты и plan_code
- `GET /billing/subscription/` — детали подписки

---

## Принцип работы (Webhook-First)

1. Фронтенд создаёт платёж → получает `confirmation_url`
2. Редирект пользователя на YooKassa
3. YooKassa отправляет webhook на бэкенд
4. Бэкенд обновляет подписку
5. Фронтенд вызывает `BillingContext.refresh()` при возврате пользователя

---

## Как тестировать

### DEV режим (mock данные)

В DEV режиме (`IS_DEV=true`) хук `useSubscriptionPlans` использует mock-данные из `__mocks__/plans.ts`.

### Проверка маршрутов

```bash
# Запуск dev-сервера
npm run dev

# Проверить:
# - http://localhost:5173/app/subscription
# - http://localhost:5173/app/settings/subscription
# - http://localhost:5173/app/settings/history
```

### Тестовый платёж (Admin)

На странице `/settings/subscription` для админов доступна карточка "Тест: Оплатить 1₽ (live)".

---

## Документация модуля

| Файл | Содержимое |
|------|------------|
| [FILE_MAP.md](./FILE_MAP.md) | Карта файлов модуля |
| [ROUTES.md](./ROUTES.md) | Описание маршрутов |
| [API_CONTRACT.md](./API_CONTRACT.md) | Контракты API |
| [UI_FLOWS.md](./UI_FLOWS.md) | Пользовательские сценарии |
| [STATE_MODEL.md](./STATE_MODEL.md) | Модель состояния |
| [ERROR_HANDLING.md](./ERROR_HANDLING.md) | Обработка ошибок |
| [DEV_NOTES.md](./DEV_NOTES.md) | Заметки для разработчиков |
| [CHANGELOG.md](./CHANGELOG.md) | История изменений |

---

## Быстрый старт для разработчика

```typescript
// Импорт страниц
import { SubscriptionPage, SubscriptionDetailsPage, PaymentHistoryPage } from './features/billing';

// Импорт компонентов
import { PlanCard, SubscriptionHeader, AdminTestPaymentCard, PaymentHistoryList } from './features/billing';
// Note: BasicPlanCard, PremiumMonthCard, PremiumProCard используются внутри PlanCard

// Импорт хуков
import { 
  useSubscriptionPlans, 
  useSubscriptionActions,
  useSubscriptionDetails,
  usePaymentHistory,
  usePaymentPolling
} from './features/billing';

// Импорт утилит
import { 
  showToast, 
  validatePlanCode,
  formatBillingDate,
  buildPlanCardState 
} from './features/billing';

// Импорт типов
import type { PlanCode } from './features/billing';
```
