# Trainer Panel — Frozen State (SSOT)

Этот документ фиксирует ТЕКУЩЕЕ состояние Trainer Panel после рефакторинга.
Цель — зафиксировать каноны архитектуры, типов и импортов.
Код менять нельзя. Документация должна соответствовать коду 1:1.

---

## 1. Архитектура данных (канон)

Backend API
↓
services/api/*
↓
Transform layer (hooks + contexts)
↓
UI components

yaml
Копировать код

### Где происходит transform
Transform данных из backend-формы в UI-форму выполняется ТОЛЬКО здесь:
- `features/trainer-panel/hooks/useApplications.ts`
- `src/contexts/ClientsContext.tsx`

UI-компоненты НЕ работают с сырыми API-типами.

---

## 2. Канон типов (SSOT)

### Статусы
- `ApplicationStatusApi = 'new' | 'viewed' | 'contacted'`
- `ApplicationStatusUi = ApplicationStatusApi | 'client'`

Правила:
- Backend НИКОГДА не возвращает `client`
- `client` — UI-only derived состояние

---

### API-типы (backend → frontend)
Используются только для приёма данных с backend.

- `ClientDetailsApi`
  - сырые поля backend (`gender: 'male' | 'female'`, `health_restrictions`, body_type id и т.д.)

- `ApplicationResponse`
  - `status: ApplicationStatusApi`
  - `details: ClientDetailsApi`

---

### UI-типы (то, что потребляет интерфейс)
Используются ТОЛЬКО в UI и после transform.

- `ClientDetailsUi`
  - локализованные строки
  - нормализованные массивы (`goals`, `limitations`, `allergies`)
  - `body_type` / `desired_body_type` как `BodyTypeInfo`

- `Application`
  - `details: ClientDetailsUi`
  - `status?: ApplicationStatusUi`
  - `date?: string` — UI-форматированная дата

---

## 3. Import Policy (строго)

### Типы
**Канон (вне feature):**
```ts
import type { Application, ApplicationResponse } 
  from 'features/trainer-panel/types';
Канон (внутри feature):

ts
Копировать код
import type { Application } from '../types';
❌ Запрещено:

импортировать типы напрямую из файлов глубже, минуя features/trainer-panel/types

дублировать типы в services/api/*

API
Канон:

ts
Копировать код
import { api } from 'services/api';
❌ Запрещено:

ts
Копировать код
import { getClients } from 'services/api/auth';
services/api/auth.ts — только аутентификация/авторизация.
Trainer API — в services/api/trainer.ts, доступ через api.

4. Правила, чтобы панель не ломалась
UI-компоненты работают только с Application и ClientDetailsUi

Backend не должен получать ApplicationStatusUi

client не хранится и не передаётся — только вычисляется в UI

Все опциональные поля (username, created_at, массивы) должны быть безопасны к отсутствию

Transform логика централизована — не дублировать её в компонентах

5. Типовой поток данных
Заявки
api.getApplications() → ApplicationResponse[]

Transform в useApplications.ts → Application[]

Рендер в UI

Клиенты
api.getClients() → API response

Transform в ClientsContext.tsx → Application[] со status: 'client'

Рендер в UI

6. Статус документа
Документ отражает текущий код (Frozen)

Рефакторинг Trainer Panel завершён

Любые изменения дальше — только инкрементальные