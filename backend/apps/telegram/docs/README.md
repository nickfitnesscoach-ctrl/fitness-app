# Telegram Backend — Документация

Полная production-документация Telegram-домена (`apps/telegram/`). Описывает аутентификацию, Bot API, панель тренера и модели данных.

---

## 🚀 С чего начать

| Роль | Читать сначала |
|------|----------------|
| **Frontend-разработчик** | [05_trainer_panel.md](./05_trainer_panel.md) → [01_overview.md](./01_overview.md) |
| **Backend-разработчик** | [01_overview.md](./01_overview.md) → [02_architecture.md](./02_architecture.md) → [06_models_and_data.md](./06_models_and_data.md) |
| **DevOps / Ops** | [DEVOPS.md](../DEVOPS.md) ← **SSOT для env и деплоя** |
| **Security** | [03_auth_and_security.md](./03_auth_and_security.md) → [DEVOPS.md](../DEVOPS.md) |
| **Новый в проекте** | [01_overview.md](./01_overview.md) → [03_auth_and_security.md](./03_auth_and_security.md) |

---

## ⚠️ Самые опасные места

> Если ошибёшься здесь — можно сломать прод или получить утечку.

| Что | Где описано | Критичность |
|-----|-------------|-------------|
| **initData подпись** | [03_auth_and_security.md](./03_auth_and_security.md#как-работает-telegram-webapp-initdata) | 🔴 Критично |
| **Debug Mode в PROD** | [03_auth_and_security.md](./03_auth_and_security.md#debug-mode) | 🔴 Критично |
| **X-Bot-Secret** | [04_bot_api.md](./04_bot_api.md#защита-x-bot-secret) | 🔴 Критично |
| **TELEGRAM_ADMINS** | [03_auth_and_security.md](./03_auth_and_security.md#telegram_admins) | 🟠 Важно |
| **Миграции моделей** | [06_models_and_data.md](./06_models_and_data.md#что-нельзя-менять-без-миграции) | 🟠 Важно |

---

## 📋 Частые задачи

| Задача | Где искать |
|--------|------------|
| Добавить нового админа | `settings.TELEGRAM_ADMINS` → [03_auth_and_security.md](./03_auth_and_security.md#telegram_admins) |
| Понять почему 403 на панели | [05_trainer_panel.md](./05_trainer_panel.md#частые-ошибки-debugging) |
| Добавить endpoint для бота | [04_bot_api.md](./04_bot_api.md) + `bot/views.py` |
| Изменить поля TelegramUser | [06_models_and_data.md](./06_models_and_data.md#telegramuser) |
| Настроить env для прода | [03_auth_and_security.md](./03_auth_and_security.md#критические-прод-настройки) |
| Интегрировать billing | [02_architecture.md](./02_architecture.md#почему-billing-вынесен-через-adapter) |

---

## 📁 Карта файлов

```
docs/
├── README.md              ← Вы здесь
├── DEVOPS.md              ← DevOps: env, deploy, smoke tests
├── ops_runbook.md         ← Инциденты, disaster recovery
├── observability.md       ← Логи, алерты, метрики
├── 01_overview.md         ← Общая картина, границы домена
├── 02_architecture.md     ← Структура кода, SSOT, зависимости
├── 03_auth_and_security.md← КРИТИЧНО: безопасность, initData
├── 04_bot_api.md          ← API для Telegram-бота
├── 05_trainer_panel.md    ← API для панели тренера (frontend)
├── 06_models_and_data.md  ← Модели, поля, миграции
└── 07_future_and_scaling.md← Масштабирование
```

---

## 🔧 Правило обновления

> **Если меняешь код в `apps/telegram/*` — обнови docs.**
