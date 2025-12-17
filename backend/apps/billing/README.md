# Billing

Система биллинга EatFit24: подписки, платежи, лимиты, интеграция с YooKassa.

## Что делает Billing

- Управляет тарифами (FREE / PRO)
- Хранит подписки пользователей
- Создаёт платежи в YooKassa
- Обрабатывает webhook и продлевает подписки
- Контролирует дневные лимиты AI-запросов
- Выполняет автопродление по cron

## Архитектура (карта)

```
billing/
├── models.py        # Модели: источник истины
├── views.py         # API для фронтенда
├── services.py      # YooKassaService + бизнес-логика
├── usage.py         # Дневные лимиты (DailyUsage)
├── throttles.py     # Rate limiting
├── urls.py          # Маршруты API
├── webhooks/        # Обработка webhook YooKassa
└── management/      # Фоновые команды
```

## Ключевые принципы

| Принцип | Описание |
|---------|----------|
| ❌ **Сумма не от клиента** | Цена берётся только из `SubscriptionPlan.price` |
| ✅ **Webhook = истина** | Платёж успешен только после webhook |
| ✅ **YooKassaService** | Единственный клиент YooKassa |
| ✅ **Атомарные лимиты** | `check_and_increment_if_allowed()` |
| ✅ **IP allowlist** | Webhook только с IP YooKassa |

## ⚠️ Запрещено

- Принимать сумму платежа с фронтенда
- Считать платёж успешным без webhook
- Создавать второй клиент YooKassa
- Менять подписку вне webhook handlers
- Добавлять оплату без webhook-подтверждения
- Возвращать legacy endpoints

## Документация

Подробная документация в `docs/`:

| Документ | Описание |
|----------|----------|
| [docs/architecture.md](./docs/architecture.md) | Архитектура модуля |
| [docs/payment-flow.md](./docs/payment-flow.md) | Поток платежа |
| [docs/subscription-lifecycle.md](./docs/subscription-lifecycle.md) | Жизненный цикл подписки |
| [docs/webhooks.md](./docs/webhooks.md) | Обработка webhook |
| [docs/security.md](./docs/security.md) | Безопасность |
| [docs/limits-and-usage.md](./docs/limits-and-usage.md) | Лимиты и использование |
| [docs/operations.md](./docs/operations.md) | Эксплуатация |
| [docs/legacy-history.md](./docs/legacy-history.md) | История legacy |
| [docs/glossary.md](./docs/glossary.md) | Глоссарий |

## Быстрый старт

1. Прочти [docs/architecture.md](./docs/architecture.md) — понять структуру
2. Прочти [docs/payment-flow.md](./docs/payment-flow.md) — понять flow денег
3. Прочти [docs/security.md](./docs/security.md) — понять ограничения

## Поток платежа (коротко)

```
1. GET /billing/plans/           → список планов
2. POST /billing/create-payment/ → создание платежа
3. Redirect → YooKassa           → оплата
4. POST /webhooks/yookassa       → подтверждение
5. GET /billing/me/              → обновлённый статус
```

## Troubleshooting

| Проблема | Куда смотреть |
|----------|---------------|
| Платёж прошёл, подписка не обновилась | `WebhookLog`, `Payment.webhook_processed_at` |
| Лимиты не работают | `DailyUsage`, `SubscriptionPlan.daily_photo_limit` |
| Webhook возвращает 403 | IP allowlist, `WEBHOOK_TRUST_XFF` |
| Автопродление не работает | `Subscription.auto_renew`, `yookassa_payment_method_id` |

Подробнее: [docs/operations.md](./docs/operations.md)
