# EatFit24 Frontend

React-приложение для EatFit24 — AI-распознавание еды и трекинг питания.

## Технологии

- **Framework**: React 18 + Vite
- **Язык**: TypeScript
- **Стили**: TailwindCSS
- **Роутинг**: React Router v6
- **Стейт**: React Context + Hooks

## Архитектура фич

Приложение использует фича-модули для изолированных доменов:

- `features/ai/` — Распознавание еды по фото, камера, загрузка (согласовано с API-контрактом)
- `features/billing/` — Подписки, платежи, биллинг UI
- `features/trainer-panel/` — Панель тренера и управление клиентами

## Структура проекта

```
src/
├── app/                    # Входная точка, провайдеры
├── pages/                  # Страницы-маршруты
├── features/               # Фича-модули
│   ├── ai/                 # AI-распознавание
│   ├── billing/            # Биллинг
│   └── trainer-panel/      # Панель тренера
├── components/             # Общие UI-компоненты
├── contexts/               # React-контексты
├── hooks/                  # Общие хуки
├── services/               # API-слой
│   └── api/                # API-клиент модули
├── shared/                 # Общие утилиты
├── types/                  # TypeScript типы
└── utils/                  # Вспомогательные функции
```

## Разработка

```bash
# Установка зависимостей
npm install

# Запуск dev-сервера
npm run dev

# Сборка для продакшена
npm run build

# Запуск линтера
npm run lint
```

## API-контракт

Документация Backend API:
- [API_CONTRACT_AI_AND_TELEGRAM.md](/docs/API_CONTRACT_AI_AND_TELEGRAM.md)

## Переменные окружения

См. `.env.example` для списка необходимых переменных окружения.
