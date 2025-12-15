# Trainer Panel API — Frozen State (SSOT)

Этот документ фиксирует ТЕКУЩЕЕ состояние API-слоя Trainer Panel после рефакторинга.
Цель — чтобы любой разработчик/агент вызывал API одинаково и не ломал канон импортов/типов.
Код менять нельзя. Документация должна соответствовать коду 1:1.

---

## 1) Канон использования API

✅ Канон:
```ts
import { api } from 'services/api';

const apps = await api.getApplications();
Допустимо (если нужен прямой импорт):

ts
Копировать код
import { getClients } from 'services/api/trainer';
❌ Запрещено:

ts
Копировать код
import { getClients } from 'services/api/auth';
services/api/auth.ts — только authentication/authorization.
Trainer endpoints находятся в services/api/trainer.ts.

2) Статусы заявок (важно)
Backend возвращает и принимает ТОЛЬКО:

ts
Копировать код
'new' | 'viewed' | 'contacted'
Backend НЕ знает про client.
client — UI-only derived состояние.

Типы:

ApplicationStatusApi = 'new' | 'viewed' | 'contacted'

ApplicationStatusUi = ApplicationStatusApi | 'client' (UI only)

3) Типы ответов (SSOT)
Типы для Trainer Panel берутся из:

ts
Копировать код
import type { ApplicationResponse } from 'features/trainer-panel/types';
Канон:

ApplicationResponse.details: ClientDetailsApi

Application.details: ClientDetailsUi (после transform в hooks/contexts)

Transform выполняется в:

features/trainer-panel/hooks/useApplications.ts

src/contexts/ClientsContext.tsx

4) Методы Trainer API (фактические)
Ниже перечислены методы, которые использует Trainer Panel.

Applications
api.getApplications(): Promise<ApplicationResponse[]>

Получить список заявок

api.updateApplicationStatus(applicationId: number, status: ApplicationStatusApi): Promise<ApplicationResponse>

Обновить статус заявки (new/viewed/contacted)

api.deleteApplication(applicationId: number): Promise<boolean>

Удалить заявку

Clients
api.getClients(): Promise<Client[]>

Получить список клиентов тренера

api.addClient(clientId: number): Promise<Client>

Добавить клиента из заявки

api.removeClient(clientId: number): Promise<boolean>

Удалить клиента из списка

Invite
api.getInviteLink(): Promise<string>

Получить инвайт-ссылку тренера

Subscribers
api.getSubscribers(): Promise<SubscribersResponse>

Получить подписчиков + статистику

5) Ошибки и безопасность вызовов (как принято сейчас)
Любой запрос может вернуть ошибку сети/401/403/500 — UI должен быть устойчивым.

В случаях, где данные не критичны (например, список), допустимо возвращать пустой массив и логировать ошибку.

В случаях, где действие критично (update/delete), ошибка должна всплыть до UI, чтобы показать сообщение пользователю.

6) Deprecated (текущее состояние)
В services/api/auth.ts могут существовать re-export trainer методов только для обратной совместимости.

Правило:

UI/feature код НЕ должен импортировать trainer функции из auth.ts.

Канон — import { api } from 'services/api' или прямой импорт из services/api/trainer.

Статус:

re-export блок в auth.ts помечен deprecated и будет удалён в следующей мажорной версии.