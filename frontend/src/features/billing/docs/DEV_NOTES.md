# DEV NOTES — Billing Feature Module

> Заметки для разработчиков: настройка, тестирование, отладка.

---

## UI Components Architecture

### Orchestrator vs Presentational Pattern

Карточки тарифных планов построены по паттерну разделения ответственности:

**Orchestrator Component (`PlanCard.tsx`):**
- Умный компонент, управляет состоянием и логикой
- Использует `buildPlanCardState()` для определения состояния карточки
- Выбирает нужный presentational компонент (`BasicPlanCard`, `PremiumMonthCard`, `PremiumProCard`)
- Передает props и обработчики событий

**Presentational Components:**
- `BasicPlanCard.tsx` — FREE план, минималистичный дизайн
- `PremiumMonthCard.tsx` — PRO_MONTHLY, темный градиент
- `PremiumProCard.tsx` — PRO_YEARLY, badge "2 МЕСЯЦА В ПОДАРОК"
- Чистые UI-компоненты без бизнес-логики
- Принимают готовые данные через props

### PlanPriceStack Component

Унифицированный компонент для предотвращения "прыгающих" ценовых блоков:

```typescript
<PlanPriceStack
    priceMain={3588}
    priceUnit="₽"
    oldPrice={4990}
    priceSubtext="за год"
    alignRight={true}
    isDark={true}
/>
```

**Особенности:**
- Фиксированный 2-row layout (row1: main+unit, row2: oldPrice+subtext)
- `min-h-[1.25rem]` на row2 предотвращает layout shifts
- Non-breaking spaces (`\u00A0`) когда oldPrice/subtext пусты
- Табулярные числа для корректного выравнивания

### Text Processing Utilities

**`cleanFeatureText(text: string)`:**
- Удаляет leading emoji (`\p{Extended_Pictographic}`)
- Удаляет replacement chars (`\uFFFD`)
- Удаляет zero-width chars и variation selectors
- Сохраняет Cyrillic и полезные символы

```typescript
// До: "✨ AI-распознавание"
// После: "AI-распознавание"
```

**`getPlanFeatureIcon(cleanText: string)`:**
- Семантическое определение иконок по содержанию текста
- Не зависит от emoji в исходных данных
- Поддерживает: Gift, FileCheck, Target, Calendar, Calculator, Zap

**Icon Mapping в Presentational Cards:**
- Каждая карточка имеет локальную функцию `getIconForFeature()`
- Использует специфичные для плана иконки и цвета
- Пример: `PremiumProCard` использует Gift (yellow), LineChart (teal), Target (pink)

---

## Как включить mock планы

В DEV режиме (`IS_DEV=true`) хук `useSubscriptionPlans` автоматически использует mock-данные.

**Конфигурация:**
- `config/env.ts` → `IS_DEV`
- `__mocks__/plans.ts` → mock-данные

**Изменение mock-данных:**

```typescript
// src/features/billing/__mocks__/plans.ts
export const mockSubscriptionPlans: SubscriptionPlan[] = [
    {
        code: 'FREE',
        display_name: 'Базовый',
        price: 0,
        // ...
    },
    // Редактируйте здесь
];
```

---

## Как тестировать без Telegram

### Вариант 1: Mock Telegram WebApp

В `lib/telegram.ts` уже настроен mock для DEV режима:

```typescript
// lib/telegram.ts
if (IS_DEV && !window.Telegram?.WebApp) {
    // Mock создаётся автоматически
}
```

### Вариант 2: Browser Debug Mode

`useAuth().isBrowserDebug` включается автоматически в DEV без Telegram.

**Поведение:**
- Платежи блокируются с сообщением "Платежи недоступны в режиме отладки"
- UI полностью функционален
- showToast использует `window.alert()`

---

## Где смотреть логи

### Console logs

```typescript
// api/billing.ts
log('Fetching billing status');
log(`Billing status: plan=${data.plan_code}, limit=${data.daily_photo_limit}`);

// hooks/*
console.error('Subscription error:', error);

// BillingContext.tsx
console.log('[BillingProvider] Waiting for auth initialization...');
console.error('[BillingProvider] Failed to fetch billing data:', error);
```

### Network tab

| Endpoint | Описание |
|----------|----------|
| `/billing/me/` | Статус и лимиты |
| `/billing/subscription/` | Детали подписки |
| `/billing/plans/` | Список тарифов |
| `/billing/create-payment/` | Создание платежа |

---

## Anti-Double-Click тестирование

Все экшены защищены от повторных кликов:

```typescript
// useSubscriptionActions.ts
const inFlightRef = useRef<Set<string>>(new Set());

const handleSelectPlan = async (planId: PlanId) => {
    const lockKey = `payment-${planId}`;
    if (inFlightRef.current.has(lockKey)) return;  // Блокировка
    
    inFlightRef.current.add(lockKey);
    try { ... } finally {
        inFlightRef.current.delete(lockKey);
    }
};
```

**Как тестировать:**
1. Добавьте `console.log` перед `return` в защитном условии
2. Быстро кликните несколько раз
3. Должен быть только один запрос

---

## Добавление нового тарифа

1. Добавьте код в `BillingPlanCode` (`types/billing.ts`)
2. Добавьте в `PLAN_CODES` (`constants/index.ts`)
3. Добавьте в `VALID_PLAN_CODES` (`utils/validation.ts`)
4. Добавьте mock в `__mocks__/plans.ts`
5. Обновите UI-логику в `planCardState.tsx`

---

## Частые проблемы

### "Платежи недоступны в режиме отладки"

**Причина:** `isBrowserDebug` или `webAppBrowserDebug` = true

**Решение:** Откройте через Telegram Mini App

### "Автопродление недоступно"

**Причина:** `autorenew_available = false` (карта не привязана)

**Решение:** Привяжите карту через "Способ оплаты"

### Unknown plan_code alert в DEV

**Причина:** Бэкенд вернул неизвестный код

**Решение:** Проверьте бэкенд или добавьте код в `VALID_PLAN_CODES`

---

## Полезные команды

```bash
# Запуск dev сервера
npm run dev

# Проверка сборки
npm run build

# TypeScript проверка
npx tsc --noEmit

# Lint
npm run lint
```

---

## Файлы для изменений

| Задача | Файлы |
|--------|-------|
| Изменить UI карточки плана | `components/BasicPlanCard.tsx`, `components/PremiumMonthCard.tsx`, `components/PremiumProCard.tsx` |
| Изменить логику выбора карточки | `components/PlanCard.tsx`, `utils/planCardState.tsx` |
| Изменить отображение цен | `components/PlanPriceStack.tsx` |
| Изменить обработку текста/иконок | `utils/text.tsx` |
| Добавить новый API endpoint | `services/api/billing.ts`, `services/api/urls.ts` |
| Изменить логику подписки | `hooks/useSubscription*.ts` |
| Добавить новый тариф | см. раздел "Добавление нового тарифа" |

