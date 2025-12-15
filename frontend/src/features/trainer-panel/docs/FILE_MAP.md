# FILE_MAP — Trainer Panel (Frozen)

**Frozen state:** 2025-12-15  
Документ отражает ТЕКУЩУЮ структуру Trainer Panel и каноны импортов.  
Цель: чтобы любой разработчик/агент быстро понял “где что лежит” и не сломал панель.

---

## 1) Структура feature

src/features/trainer-panel/
├── pages/
│ ├── ApplicationsPage.tsx
│ ├── ClientsPage.tsx
│ ├── InviteClientPage.tsx
│ └── TrainerPanelPage.tsx
├── components/
│ ├── applications/
│ │ ├── ApplicationCard.tsx
│ │ └── ApplicationDetails.tsx
│ ├── clients/
│ │ ├── ClientCard.tsx
│ │ └── ClientDetails.tsx
│ ├── Layout.tsx
│ └── Dashboard.tsx
├── hooks/
│ ├── useApplications.ts # загрузка + transform заявок (API → UI)
│ └── useClientsList.ts # список/поиск/фильтр клиентов (UI слой)
├── constants/
│ ├── applications.ts # справочники/описания (activity/training/etc)
│ └── invite.ts # invite-related константы (если используются)
├── types/
│ ├── application.ts # SSOT типов Trainer Panel (API + UI)
│ └── index.ts # re-export типов (канон импорта типов)
└── docs/
├── TRAINER_PANEL.md # главный канон (архитектура/типы/импорты)
├── TRAINER_API.md # API канон (методы, статусы, usage)
├── FILE_MAP.md # этот файл
└── AUDIT_REPORT.md # фиксация “после рефактора”

yaml
Копировать код

---

## 2) Связанные файлы вне feature (важное)

src/
├── contexts/
│ └── ClientsContext.tsx # клиенты тренера + transform (API → UI)
├── services/api/
│ ├── trainer.ts # SSOT trainer endpoints (implementation)
│ ├── auth.ts # auth endpoints (+ deprecated re-exports)
│ ├── index.ts # export { api } — канон использования
│ ├── client.ts # fetch wrappers / headers / retry / logging
│ ├── urls.ts # URLS для API
│ └── types.ts # общие API типы (не trainer-panel домен)
└── App.tsx # роутинг /panel/*

yaml
Копировать код

---

## 3) Каноны импортов (строго)

### 3.1 Типы (SSOT)

**SSOT:** `src/features/trainer-panel/types/`

✅ Канон (внешние файлы: `src/contexts/*`, `src/services/*`, любые “не внутри feature”):
```ts
import type { Application, ApplicationResponse, ClientDetailsUi } 
  from 'features/trainer-panel/types';
✅ Канон (внутри feature: src/features/trainer-panel/**):

ts
Копировать код
import type { Application } from '../types';
❌ Запрещено:

импортировать типы из конкретных файлов глубже, минуя features/trainer-panel/types

дублировать доменные типы Trainer Panel внутри services/api/*

3.2 API (канон вызовов)
SSOT implementation: src/services/api/trainer.ts
SSOT usage: import { api } from 'services/api'

✅ Канон:

ts
Копировать код
import { api } from 'services/api';
await api.getApplications();
Допустимо (редко, если нужен прямой импорт):

ts
Копировать код
import { getClients } from 'services/api/trainer';
❌ Запрещено:

ts
Копировать код
import { getClients } from 'services/api/auth';
3.3 Constants
✅ Внутри feature:

ts
Копировать код
import { ACTIVITY_DESCRIPTIONS } from '../constants/applications';
✅ Из внешних файлов:

ts
Копировать код
import { TRAINER_INVITE_LINK } from 'features/trainer-panel/constants/invite';
4) Где происходит transform (самое важное)
Transform — это место, где сырые данные backend (*Api, ApplicationResponse) превращаются в UI модель (Application, ClientDetailsUi).

src/features/trainer-panel/hooks/useApplications.ts

api.getApplications() → ApplicationResponse[]

transform → Application[]

src/contexts/ClientsContext.tsx

api.getClients() → API response

transform → Application[] со статусом client (UI-only)

Правило: UI компоненты должны потреблять только UI модель.

5) Quick Reference (куда лезть)
Задача	Где менять
Добавить страницу панели	features/trainer-panel/pages/ + роут в App.tsx
Изменить UI карточек/деталей	features/trainer-panel/components/*
Изменить загрузку/transform заявок	features/trainer-panel/hooks/useApplications.ts
Изменить фильтр/поиск клиентов	features/trainer-panel/hooks/useClientsList.ts
Изменить transform клиентов	src/contexts/ClientsContext.tsx
Добавить/изменить API endpoint	src/services/api/trainer.ts (+ экспорт через api)
Добавить/изменить доменные типы	features/trainer-panel/types/application.ts + types/index.ts
Добавить справочники/маппинги	features/trainer-panel/constants/*