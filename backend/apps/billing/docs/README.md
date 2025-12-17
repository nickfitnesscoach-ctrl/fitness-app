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
| [**RECURRING_SWITCH.md**](./RECURRING_SWITCH.md) | **⚠️ Переключатель recurring/one-time** |
| [**KNOWN_LIMITATIONS.md**](./KNOWN_LIMITATIONS.md) | **⚠️ Известные ограничения** |
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

## ⚠️ Важные ограничения (2025-12-17)

### Recurring платежи: контролируются флагом `BILLING_RECURRING_ENABLED`

**Текущий статус:** `BILLING_RECURRING_ENABLED=false` (ONE_TIME режим)

**Причина:** YooKassa возвращает 403 Forbidden при `save_payment_method=true` (recurring не активирован на аккаунте)

**Что это значит:**
- ✅ Единоразовые платежи работают
- ❌ Автопродление подписок недоступно
- ❌ Привязка карты недоступна

**Как включить обратно:**
1. Активировать recurring в личном кабинете YooKassa
2. Изменить `BILLING_RECURRING_ENABLED=true` в `/opt/EatFit24/.env`
3. Перезапустить: `docker compose restart backend celery-worker`

**Документация:**
- [RECURRING_SWITCH.md](./RECURRING_SWITCH.md) — полная инструкция
- [KNOWN_LIMITATIONS.md](./KNOWN_LIMITATIONS.md) — все ограничения
