# Документация Billing

Система биллинга EatFit24: подписки, платежи, лимиты, интеграция с YooKassa.

## Содержание

| Документ | Описание |
|----------|----------|
| [architecture.md](./architecture.md) | Архитектура модуля |
| [payment-flow.md](./payment-flow.md) | Поток платежа |
| [subscription-lifecycle.md](./subscription-lifecycle.md) | Жизненный цикл подписки |
| [webhooks.md](./webhooks.md) | Обработка webhook |
| [security.md](./security.md) | Безопасность |
| [limits-and-usage.md](./limits-and-usage.md) | Лимиты и использование |
| [operations.md](./operations.md) | Эксплуатация |
| [legacy-history.md](./legacy-history.md) | История legacy |
| [glossary.md](./glossary.md) | Глоссарий |

## Быстрый старт

1. Прочитай [architecture.md](./architecture.md) — понять структуру
2. Прочитай [payment-flow.md](./payment-flow.md) — понять flow денег
3. Прочитай [security.md](./security.md) — понять ограничения

## Ключевые принципы

- **Webhook = источник истины** — платёж успешен только после webhook
- **Цена из БД** — сумма никогда не приходит с фронта
- **Атомарные лимиты** — защита от race condition
- **YooKassaService** — единственный клиент YooKassa
