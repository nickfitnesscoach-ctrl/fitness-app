# Trainer Panel — Audit Report (Frozen)

## Цель
Зафиксировать текущее состояние Trainer Panel после рефакторинга так, чтобы:
- код и документация совпадали 1:1
- не было обратных зависимостей
- правила импортов и типов были едины

## Итоговый статус
- TypeScript: зелёный (`type-check` ✅)
- Lint: зелёный (`lint` ✅)
- Build: зелёный (`build` ✅)
- Архитектура данных приведена к единому канону:
  Backend API → services/api → transform (hooks/contexts) → UI

## Что было (проблема)
- UI-компоненты ожидали “UI-поля”, но типы описывали только “сырой backend”.
- Были несогласованные импорты и неоднозначные источники типов.
- Из-за этого TypeScript либо молчал (через any/дыры), либо падал при усилении типов.

## Что стало (решение)
### 1) SSOT типов для trainer panel
Типы зафиксированы в `features/trainer-panel/types`:

- API слой:
  - `ClientDetailsApi`
  - `ApplicationResponse` (status: `ApplicationStatusApi`, details: `ClientDetailsApi`)

- UI слой:
  - `ClientDetailsUi`
  - `Application` (details: `ClientDetailsUi`, status: `ApplicationStatusUi`, date optional)

### 2) Централизованный transform
Transform из API формы в UI форму выполняется ТОЛЬКО в:
- `features/trainer-panel/hooks/useApplications.ts`
- `src/contexts/ClientsContext.tsx`

### 3) Канон импортов
- Типы: импортировать из `features/trainer-panel/types`
- API: использовать `import { api } from 'services/api'`
- Trainer функции из `services/api/auth` — запрещены (deprecated)

## Post-change verification (что проверено)
- Нет импорта trainer функций из `services/api/auth` в UI/feature коде
- Типы trainer panel не зависят от `services/api/*`
- Статус `client` используется только в UI, не уходит на backend
- `npm run type-check` / `npm run lint` / `npm run build` — зелёные

## Канон (6 пунктов)
1) Backend не возвращает `client`.
2) `ClientDetailsApi` — сырой backend, `ClientDetailsUi` — только для UI.
3) Transform только в `useApplications.ts` и `ClientsContext.tsx`.
4) UI работает только с UI-моделью (`Application`, `ClientDetailsUi`).
5) API вызываем через `api` из `services/api`.
6) Типы импортируем только из `features/trainer-panel/types`.
