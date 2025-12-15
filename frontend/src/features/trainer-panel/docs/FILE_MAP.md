# Trainer Panel: File Map

Краткий справочник ключевых файлов панели тренера.

---

## Feature Files (`features/trainer-panel/`)

### Pages

| Файл | Назначение |
|------|------------|
| `pages/ApplicationsPage.tsx` | Список заявок с фильтрами, поиском, переходом к деталям |
| `pages/ClientsPage.tsx` | Список клиентов тренера с поиском |
| `pages/InviteClientPage.tsx` | Страница генерации ссылки-приглашения |
| `pages/SubscribersPage.tsx` | Статистика подписчиков и доходов |

### Components

| Файл | Назначение |
|------|------------|
| `components/Dashboard.tsx` | Главная панели с навигационными кнопками |
| `components/Layout.tsx` | Layout с авторизацией и нижней навигацией |
| `components/applications/ApplicationCard.tsx` | Карточка заявки в списке |
| `components/applications/ApplicationDetails.tsx` | Детальный просмотр заявки |
| `components/clients/ClientCard.tsx` | Карточка клиента в списке |
| `components/clients/ClientDetails.tsx` | Детальный просмотр клиента |

### Hooks

| Файл | Назначение |
|------|------------|
| `hooks/useApplications.ts` | Загрузка, фильтрация, CRUD заявок |
| `hooks/useClientsList.ts` | Фильтрация клиентов, действия с ними |

### Types

| Файл | Назначение |
|------|------------|
| `types/application.ts` | `Application`, `ApplicationDetails`, `ApplicationStatusApi`, `ApplicationStatusUi` |
| `types/index.ts` | **SSOT** Re-export типов — импорт только отсюда |

### Constants

| Файл | Назначение |
|------|------------|
| `constants/applications.ts` | Маппинги данных (активность, цели, ограничения) |
| `constants/invite.ts` | Ссылка приглашения из env |

### Documentation

| Файл | Назначение |
|------|------------|
| `docs/TRAINER_PANEL.md` | Обзор, flows, Import Policy, debug guide |
| `docs/TRAINER_API.md` | Endpoints, типы, error handling, Migration Notes |
| `docs/AUDIT_REPORT.md` | Отчёт аудита |
| `docs/FILE_MAP.md` | Этот файл |

---

## Related Files Outside Feature

### API Layer (`services/api/`)

| Файл | Назначение |
|------|------------|
| `trainer.ts` | **SSOT** — все trainer API функции |
| `auth.ts` | Авторизация + ⚠️ deprecated re-export trainer |
| `index.ts` | Экспорт всех модулей + `api` объект |
| `urls.ts` | URL endpoints |
| `client.ts` | Base fetch, headers, error classes |
| `types.ts` | Общие API типы |

### Context

| Файл | Назначение |
|------|------------|
| `contexts/ClientsContext.tsx` | Глобальное состояние клиентов |

### Shared Components (используются в trainer-panel)

| Файл | Назначение |
|------|------------|
| `components/Avatar.tsx` | Аватар пользователя |
| `components/common/InfoItem.tsx` | Info card для деталей |

### Routing

| Файл | Назначение |
|------|------------|
| `App.tsx` | Маршруты `/panel/*` |

---

## Import Guidelines

### Types (SSOT: `features/trainer-panel/types/`)

```typescript
// ✅ From external file (contexts/, services/) - use path alias
import type { Application, ApplicationStatusApi } from 'features/trainer-panel/types';

// ✅ Within feature (hooks, components) - relative paths OK
import { Application } from '../types/application';
import type { Application } from '../types';  // via index re-export
```

### API (SSOT: `services/api/trainer.ts`)

```typescript
// ✅ Canon: через api объект
import { api } from 'services/api';
await api.getApplications();

// ✅ Допустимо: прямой импорт из trainer
import { getApplications } from 'services/api/trainer';

// ❌ Запрещено: импорт из auth.ts (deprecated)
import { getApplications } from 'services/api/auth';
```

### Constants

```typescript
// ✅ Внутри feature (относительный путь)
import { ACTIVITY_DESCRIPTIONS } from '../constants/applications';

// ✅ Снаружи feature (концептуальный путь)
import { ACTIVITY_DESCRIPTIONS } from 'features/trainer-panel/constants/applications';
```

> [!WARNING]
> Не импортировать trainer функции из `auth.ts` — deprecated!
> См. TRAINER_API.md → Migration Notes

---

## Quick Reference

| Нужно | Файл |
|-------|------|
| Добавить новую страницу | `pages/` + обновить `App.tsx` |
| Добавить API endpoint | `services/api/trainer.ts` |
| Добавить тип | `types/application.ts` + `types/index.ts` |
| Добавить маппинг данных | `constants/applications.ts` |
| Изменить layout/навигацию | `components/Layout.tsx` |

