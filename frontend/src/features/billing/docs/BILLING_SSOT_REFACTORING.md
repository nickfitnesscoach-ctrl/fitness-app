# Billing SSOT Refactoring — v2.0

## Summary

Billing-модуль полностью разделён на **billing truth** (бэкенд) и **marketing copy** (фронтенд).

- **Бэкенд**: цены, скидки, лимиты — редактируются в Django Admin
- **Фронтенд**: названия, тексты фич, бейджи — редактируются в `planCopy.ts`

**Изменение цен не требует деплоя фронта. Изменение текстов не требует деплоя бэка.**

---

## Архитектура SSOT

```
┌─────────────────────────────────────────────────────────────────┐
│                        BILLING TRUTH                             │
│                    (Backend / Django Admin)                      │
├─────────────────────────────────────────────────────────────────┤
│  price         │  old_price      │  duration_days  │  limits    │
│  2990₽         │  4990₽          │  365            │  null      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ GET /billing/plans/
                              │
┌─────────────────────────────────────────────────────────────────┐
│                       MARKETING COPY                             │
│                  (Frontend / planCopy.ts)                        │
├─────────────────────────────────────────────────────────────────┤
│  displayName   │  features[]     │  badge          │  order     │
│  "PRO Год"     │  ["Все PRO..."] │  "ВЫБОР..."     │  1         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Где что менять

| Хочу изменить | Где менять | Деплой |
|---------------|------------|--------|
| Цену тарифа | Django Admin → SubscriptionPlan | Не нужен |
| Скидку (old_price) | Django Admin → SubscriptionPlan | Не нужен |
| Название ("PRO Год") | `config/planCopy.ts` | Только фронт |
| Список фич на карточке | `config/planCopy.ts` | Только фронт |
| Бейдж "Выбор пользователей" | `config/planCopy.ts` | Только фронт |
| Порядок карточек | `config/planCopy.ts` (order) | Только фронт |

---

## Файлы

### Backend

| Файл | Изменение |
|------|-----------|
| `models.py` | Добавлено поле `old_price` (PositiveIntegerField, nullable) |
| `serializers.py` | Убран PLAN_CONFIG, deprecated поля возвращают neutral values |
| `admin.py` | `old_price` добавлен в list_display и fieldset |
| `migrations/0017_*` | Миграция для old_price |

### Frontend

| Файл | Изменение |
|------|-----------|
| `config/planCopy.ts` | **NEW** — SSOT для маркетинговых текстов |
| `components/PlanCard.tsx` | Использует `getPlanCopy()` для текстов |
| `pages/SubscriptionPage.tsx` | Сортировка через `copy.order` |
| `__mocks__/subscriptionPlans.ts` | Убраны features, is_popular |

---

## planCopy.ts — SSOT маркетинга

```typescript
// config/planCopy.ts

export interface PlanCopyConfig {
  displayName: string;      // "PRO Год"
  badge?: string;           // "ВЫБОР ПОЛЬЗОВАТЕЛЕЙ"
  features: string[];       // ["Все функции PRO-доступа", ...]
  oldPrice?: number;        // 4990 (fallback если БД пустая)
  order: number;            // 1 = первый, 2 = второй, ...
}

export const PLAN_COPY: Record<string, PlanCopyConfig> = {
  PRO_YEARLY: {
    displayName: 'PRO Год',
    badge: 'ВЫБОР ПОЛЬЗОВАТЕЛЕЙ',
    features: [
      'Все функции PRO-доступа',
      '60-мин стратегия с тренером (5000₽)',
      'Аудит твоего питания',
      'План выхода на цель',
    ],
    oldPrice: 4990,
    order: 1,
  },
  PRO_MONTHLY: {
    displayName: 'PRO Месяц',
    features: [
      'Полная свобода питания',
      'Мгновенный подсчет калорий',
      'Анализ прогресса и привычек',
      'Адаптивный план под твою цель',
    ],
    order: 2,
  },
  FREE: {
    displayName: 'Базовый',
    features: [
      '3 AI-распознавания в день',
      'Базовый расчет КБЖУ',
      'История питания (7 дней)',
    ],
    order: 3,
  },
};

export function getPlanCopy(code: string): PlanCopyConfig;
```

---

## API Contract

### GET /api/v1/billing/plans/

```json
{
  "code": "PRO_YEARLY",
  "display_name": "PRO Yearly",    // ⚠️ DEPRECATED — используй copy.displayName
  "price": 2990,                   // ✅ Billing truth
  "old_price": 4990,               // ✅ Billing truth (nullable)
  "duration_days": 365,            // ✅ Billing truth
  "features": [],                  // ⚠️ DEPRECATED — используй copy.features
  "is_popular": false,             // ⚠️ DEPRECATED — используй copy.badge
  "daily_photo_limit": null,       // ✅ Limits
  "history_days": -1,              // ✅ Limits
  ...
}
```

> [!WARNING]
> **Deprecated поля удаляются после 2026-02-15:**
> - `features` → всегда `[]`
> - `is_popular` → всегда `false`
> - `display_name` → значение из БД (не используй для UI)

---

## Fallback Chain для old_price

```
plan.old_price (API/БД)
    ↓ если null
copy.oldPrice (planCopy.ts)
    ↓ если undefined
undefined (не показываем скидку)
```

**Валидация:** скидка показывается только если `old_price > price`.

---

## Миграция

После деплоя бэкенда:

```bash
cd backend
uv run python manage.py migrate
```

Затем в Django Admin:
1. Открыть SubscriptionPlan → PRO_YEARLY
2. Установить `old_price = 4990`
3. Сохранить

---

## Types SSOT (без изменений)

```typescript
// billing/types.ts
export const PLAN_CODES = ['FREE', 'PRO_MONTHLY', 'PRO_YEARLY'] as const;
export type PlanCode = (typeof PLAN_CODES)[number];

export function isPlanCode(value: unknown): value is PlanCode;
export function toPlanCodeOrFree(value: unknown): PlanCode;
export function isProPlanCode(code: PlanCode): boolean;
```

---

## Verification

| Check | Status |
|-------|--------|
| TypeScript build | ✅ |
| old_price в Django Admin | ✅ |
| Deprecated fields отдают neutral | ✅ |
| Fallback chain работает | ✅ |
| Стабильная сортировка | ✅ |

---

> **Версия:** 2.0 (2026-01-13)
> 
> **Ключевые файлы:**
> - Types: `billing/types.ts`
> - Marketing: `billing/config/planCopy.ts`
> - Routing: `billing/components/PlanCard.tsx`
