# Trainer Panel

Панель тренера для управления клиентами, заявками и подписчиками.

## Purpose

Trainer Panel — это отдельная подсистема приложения EatFit24, предназначенная для тренеров:

- Просмотр и управление заявками (лиды)
- Ведение списка клиентов
- Генерация ссылок-приглашений
- Аналитика подписчиков и доходов

## Folder Map

```
features/trainer-panel/
├── components/           # UI компоненты
│   ├── Dashboard.tsx          # Главная дашборд
│   ├── Layout.tsx             # Layout с навигацией
│   ├── applications/          # Компоненты заявок
│   │   ├── ApplicationCard.tsx
│   │   └── ApplicationDetails.tsx
│   └── clients/               # Компоненты клиентов
│       ├── ClientCard.tsx
│       └── ClientDetails.tsx
├── pages/                # Страницы
│   ├── ApplicationsPage.tsx   # Список заявок
│   ├── ClientsPage.tsx        # Список клиентов
│   ├── InviteClientPage.tsx   # Приглашение клиента
│   └── SubscribersPage.tsx    # Подписчики и статистика
├── hooks/                # Хуки
│   ├── useApplications.ts     # Управление заявками
│   └── useClientsList.ts      # Управление клиентами
├── constants/            # Константы
│   ├── applications.ts        # Маппинги данных
│   └── invite.ts              # Ссылка приглашения
├── types/                # Типы TypeScript
│   ├── application.ts         # Application, ApplicationDetails, Status types
│   └── index.ts               # Re-export всех типов
└── docs/                 # Документация
    ├── TRAINER_PANEL.md       # Этот файл
    ├── TRAINER_API.md         # Документация API
    ├── AUDIT_REPORT.md        # Отчёт аудита
    └── FILE_MAP.md            # Карта всех файлов
```

## Key Pages

| Page | Responsibility | Uses Hooks | Uses API |
|------|----------------|-----------|----------|
| `ApplicationsPage` | Список заявок с фильтрами и поиском | `useApplications` | `api.getApplications`, `api.updateApplicationStatus`, `api.deleteApplication` |
| `ClientsPage` | Список клиентов с поиском | `useClientsList` | через `ClientsContext` → `api.getClients` |
| `InviteClientPage` | Форма генерации ссылки-приглашения | — | `api.getInviteLink` (при необходимости) |
| `SubscribersPage` | Статистика подписчиков | — | `api.getSubscribers` |

## Key Flows

### 1. Applications Flow
```
ApplicationsPage → useApplications hook → api.* → UI
  ├── Загрузка: getApplications()
  ├── Смена статуса: updateApplicationStatus()
  ├── Удаление: deleteApplication()
  └── Конвертация в клиента: addClient() через ClientsContext
```

### 2. Clients Flow
```
ClientsPage → useClientsList → ClientsContext → api.* → UI
  ├── Загрузка: getClients()
  ├── Удаление: removeClient()
  └── Открытие чата: через Telegram WebApp
```

### 3. Invite Flow
```
InviteClientPage → TRAINER_INVITE_LINK (из env) → UI
  └── Копирование или отправка в Telegram
```

### 4. Subscribers Flow
```
SubscribersPage → api.getSubscribers() → UI
  └── Фильтрация по типу подписки (free/monthly/yearly)
```

## Import Policy

> [!IMPORTANT]
> Строгие правила импортов для Trainer Panel

### Types

**SSOT:** `features/trainer-panel/types/`

```typescript
// ✅ Правильно — из внешнего файла (contexts/, services/)
import type { Application, ApplicationStatusApi } from 'features/trainer-panel/types';

// ✅ Правильно — внутри feature (hooks, components)
import { Application } from '../types/application';
// или через re-export:
import type { Application } from '../types';
```

> [!NOTE]
> **Status types:**
> - `ApplicationStatusApi = 'new' | 'viewed' | 'contacted'` — from backend
> - `ApplicationStatusUi = ApplicationStatusApi | 'client'` — includes UI-derived state
> - Backend **NEVER** returns `'client'` — this is set locally in `ClientsContext`

### API

**SSOT:** `services/api/trainer.ts`

```typescript
// ✅ Canon — через api объект
import { api } from 'services/api';
await api.getApplications();

// ✅ Допустимо — прямой импорт из trainer
import { getApplications } from 'services/api/trainer';

// ❌ Запрещено — из auth.ts (deprecated, will be removed in v2.0)
import { getApplications } from 'services/api/auth';
```

### Constants

**SSOT:** `features/trainer-panel/constants/`

```typescript
// ✅ Правильно — из feature constants (относительно компонента внутри feature)
import { ACTIVITY_DESCRIPTIONS } from '../constants/applications';
import { TRAINER_INVITE_LINK } from '../constants/invite';

// ✅ Правильно — из внешнего файла (например contexts/)
import { ACTIVITY_DESCRIPTIONS } from '../features/trainer-panel/constants/applications';
```

### Прямой fetch запрещён

```typescript
// ❌ Запрещено в UI компонентах
fetch('/api/v1/telegram/applications/');

// ✅ Только через api объект
api.getApplications();
```

> [!WARNING]
> `auth.ts` trainer re-exports are **DEPRECATED** and will be removed in v2.0.
> See TRAINER_API.md → Migration Notes.

## Safe Edits

✅ **Можно безопасно менять:**
- Стили и верстку компонентов
- Тексты и лейблы
- Добавление новых фильтров/сортировок
- Расширение типов новыми полями

⚠️ **Осторожно:**
- Изменение API endpoints — требует синхронизации с backend
- Изменение структуры типов — проверить все места использования
- Изменение `ClientsContext` — используется глобально

## Debug Guide

### DevTools Network

Что смотреть:
- `GET /api/v1/telegram/applications/` — заявки
- `GET /api/v1/telegram/clients/` — клиенты
- `GET /api/v1/telegram/subscribers/` — подписчики
- `PATCH /api/v1/telegram/applications/{id}/status/` — смена статуса
- `POST /api/v1/telegram/clients/{id}/add/` — добавление клиента

### Типичные ошибки

| Ошибка | Причина | Решение |
|--------|---------|---------|
| 401 Unauthorized | Истекла сессия Telegram | Переоткрыть приложение из бота |
| 403 Forbidden | Нет прав тренера | Проверить роль пользователя на backend |
| Пустой список | Нет данных | Проверить есть ли заявки/клиенты в БД |

## Related Files Outside Feature

- `contexts/ClientsContext.tsx` — глобальный контекст клиентов
- `services/api/trainer.ts` — **SSOT** API слой trainer panel
- `services/api/auth.ts` — авторизация в панель тренера (+ deprecated re-exports)
- `App.tsx` — маршрутизация `/panel/*`

