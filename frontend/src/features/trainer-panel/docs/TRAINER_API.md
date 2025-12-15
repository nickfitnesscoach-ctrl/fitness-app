# Trainer API

API слой для Trainer Panel. Все запросы панели тренера.

## Purpose

Модуль `services/api/trainer.ts` — **SSOT** (Single Source of Truth) для всех Trainer Panel API:
- Единая точка входа для trainer endpoints
- Типизированные ответы
- Нормализованная обработка ошибок
- Логирование запросов

## Base Client

| Параметр | Значение |
|----------|----------|
| **Base URL** | `/api/v1` (через Vite proxy / nginx) |
| **Auth** | `X-Telegram-Init-Data` header (автоматически из `getHeaders()`) |
| **Timeout** | 150 секунд |
| **Retry** | 3 попытки с exponential backoff |

## Endpoints Map

### Applications (Заявки)

| Function | Method + URL | Params | Response Type | Used In |
|----------|-------------|--------|---------------|---------|
| `getApplications()` | `GET /telegram/applications/` | — | `ApplicationResponse[]` | `useApplications` |
| `deleteApplication(id)` | `DELETE /telegram/applications/{id}/` | `id: number` | `boolean` | `useApplications` |
| `updateApplicationStatus(id, status)` | `PATCH /telegram/applications/{id}/status/` | `id: number`, `status: ApplicationStatusApi` | `ApplicationResponse` | `useApplications` |

### Clients (Клиенты)

| Function | Method + URL | Params | Response Type | Used In |
|----------|-------------|--------|---------------|---------|
| `getClients()` | `GET /telegram/clients/` | — | `Client[]` | `ClientsContext` |
| `addClient(clientId)` | `POST /telegram/clients/{id}/add/` | `clientId: number` | `Client` | `ClientsContext` |
| `removeClient(clientId)` | `DELETE /telegram/clients/{id}/` | `clientId: number` | `boolean` | `ClientsContext`, `useClientsList` |

### Invite (Приглашения)

| Function | Method + URL | Params | Response Type | Used In |
|----------|-------------|--------|---------------|---------|
| `getInviteLink()` | `GET /telegram/invite-link/` | — | `string` (link) | при необходимости |

### Subscribers (Подписчики)

| Function | Method + URL | Params | Response Type | Used In |
|----------|-------------|--------|---------------|---------|
| `getSubscribers()` | `GET /telegram/subscribers/` | — | `SubscribersResponse` | `SubscribersPage` |

## Types

### Status Types (важно!)

> [!IMPORTANT]
> **Backend НИКОГДА не возвращает `'client'`** — это UI derived state.

```typescript
// API status — что возвращает backend
type ApplicationStatusApi = 'new' | 'viewed' | 'contacted';

// UI status — расширение для фронтенда
type ApplicationStatusUi = ApplicationStatusApi | 'client';
// 'client' устанавливается локально когда заявка добавлена в клиенты
```

### Application Types

```typescript
// Ответ от API (status = ApplicationStatusApi)
interface ApplicationResponse {
    id: number;
    telegram_id: number;
    first_name: string;
    last_name?: string;
    username?: string;
    photo_url?: string;
    status: ApplicationStatusApi;  // НЕ 'client'!
    created_at: string;
    details: ClientDetails;
}

// Для UI (status включает 'client')
interface Application {
    // ...same fields...
    status?: ApplicationStatusUi;  // может быть 'client'
}
```

### Other Types

```typescript
interface Client {
    id: number;
    telegram_id: number;
    first_name: string;
    last_name?: string;
    username?: string;
    photo_url?: string;
    created_at: string;
    details: ClientDetails;
}

interface Subscriber {
    id: number;
    telegram_id: number;
    first_name: string;
    last_name?: string;
    username?: string;
    plan_type: 'free' | 'monthly' | 'yearly';
    subscribed_at?: string;
    expires_at?: string;
    is_active: boolean;
}

interface SubscribersResponse {
    subscribers: Subscriber[];
    stats: {
        total: number;
        free: number;
        monthly: number;
        yearly: number;
        revenue: number;
    };
}
```

## Errors

### Error Format

Все API ошибки нормализуются через `ApiError`:

```typescript
interface ApiError {
    status: number;     // HTTP status code
    code: string;       // Код ошибки (e.g., 'TIMEOUT', 'UNKNOWN_ERROR')
    message: string;    // Человекочитаемое сообщение
    details: object;    // Дополнительные данные
}
```

### UI Error Handling

| Status | Код | UI реакция |
|--------|-----|------------|
| 401 | `session_expired` | Показать "Откройте приложение заново из Telegram" |
| 403 | `forbidden` | Показать "Нет прав доступа к панели тренера" |
| 404 | `not_found` | Показать "Данные не найдены" |
| 429 | `rate_limit` | Показать "Слишком много запросов, подождите" |
| 500 | `server_error` | Показать "Ошибка сервера, попробуйте позже" |
| timeout | `TIMEOUT` | Показать "Превышено время ожидания" |

## Do / Don't

### ✅ Do

- Импортировать API через `import { api } from 'services/api'`
- Использовать типизированные функции
- Обрабатывать ошибки через try/catch
- Логировать действия через `log()`

### ❌ Don't

- Не делать `fetch()` напрямую из компонентов
- Не хардкодить URLs
- Не игнорировать ошибки
- Не использовать `any` для типов
- **Не импортировать trainer функции из `auth.ts`** (deprecated)

## Usage Examples

Стандартный способ — через `api` объект:

```typescript
import { api } from '../services/api';

// В хуке
const loadApplications = async () => {
    try {
        const data = await api.getApplications();
        setApplications(data);
    } catch (error) {
        console.error('Failed to load:', error);
    }
};

// В контексте
const loadClients = async () => {
    const data = await api.getClients();
    // data is typed as Client[]
};
```

## Migration Notes

### Чеклист миграции импортов

> [!WARNING]
> `auth.ts` re-exports are **DEPRECATED** and will be removed in v2.0

**Статус миграции: ✅ Завершено**

1. ✅ `services/api/index.ts` — использует `trainer.*` напрямую
2. ✅ `useApplications.ts` — использует `api.getApplications()`
3. ✅ `ClientsContext.tsx` — использует `api.getClients()`
4. ✅ `SubscribersPage.tsx` — использует `api.getSubscribers()`

**Для удаления в v2.0:**
- [ ] Удалить deprecated re-export блок из `services/api/auth.ts`
- [ ] Проверить отсутствие импортов trainer функций из auth.ts
- [ ] Обновить эту документацию

