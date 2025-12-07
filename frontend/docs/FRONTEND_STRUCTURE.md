# Структура Frontend EatFit24

Простое описание: что где лежит и зачем нужно.

---

## Корневая папка `frontend/`

```
frontend/
├── src/                 # Исходный код приложения
├── public/              # Статические файлы (лендинг, картинки)
├── dist/                # Собранное приложение (создаётся при build)
├── node_modules/        # Зависимости npm (не в git)
├── docs/                # Документация
│
├── index.html           # Главная HTML-страница (точка входа)
├── package.json         # Зависимости и npm-скрипты
├── package-lock.json    # Точные версии зависимостей
│
├── vite.config.js       # Настройки сборщика Vite
├── tsconfig.json        # Настройки TypeScript
├── tsconfig.node.json   # TypeScript для Node.js скриптов
├── tailwind.config.js   # Настройки Tailwind CSS
├── postcss.config.js    # Настройки PostCSS (нужен для Tailwind)
├── eslint.config.js     # Настройки линтера (проверка кода)
│
├── Dockerfile           # Инструкция сборки Docker-образа
├── nginx.conf           # Nginx конфиг для production (в Docker)
├── nginx.local.conf     # Nginx конфиг для локальной разработки
│
├── .env.example         # Шаблон переменных окружения
├── .env.development     # Переменные для разработки
├── .env.production      # Переменные для production
├── .gitignore           # Файлы, которые не попадают в git
├── .dockerignore        # Файлы, которые не попадают в Docker
│
└── README.md            # Описание проекта
```

---

## Папка `src/` — Исходный код

```
src/
├── components/    # Переиспользуемые UI-компоненты
├── pages/         # Страницы приложения (роуты)
├── hooks/         # Кастомные React-хуки
├── contexts/      # React Context (глобальное состояние)
├── services/      # API-запросы к бэкенду
├── utils/         # Вспомогательные функции
├── types/         # TypeScript типы
├── constants/     # Константы (URL, лимиты и т.д.)
├── lib/           # Внешние библиотеки/утилиты
├── assets/        # Картинки, иконки, шрифты
├── test/          # Тесты
│
├── App.tsx        # Главный компонент приложения
├── App.css        # Глобальные стили
├── main.tsx       # Точка входа React
├── index.css      # Базовые стили (Tailwind)
├── mockTelegram.ts # Мок Telegram WebApp для разработки в браузере
└── vite-env.d.ts  # TypeScript типы для Vite
```

---

## Что за что отвечает

### Конфигурационные файлы

| Файл | Зачем нужен |
|------|-------------|
| `package.json` | Список зависимостей и команды (`npm run dev`, `npm run build`) |
| `vite.config.js` | Настройки сборки: пути, плагины, proxy для API |
| `tsconfig.json` | Настройки TypeScript: строгость проверок, пути импортов |
| `tailwind.config.js` | Кастомные цвета, шрифты, точки брейкпоинтов |
| `eslint.config.js` | Правила проверки кода (ошибки, стиль) |
| `postcss.config.js` | Обработка CSS (нужен для работы Tailwind) |

### Docker и деплой

| Файл | Зачем нужен |
|------|-------------|
| `Dockerfile` | Как собрать Docker-образ: установить npm, собрать билд, запустить nginx |
| `nginx.conf` | Роутинг в production: SPA-fallback, proxy API, заголовки безопасности |
| `nginx.local.conf` | То же для локального Docker-тестирования |

### Переменные окружения (.env)

| Файл | Зачем нужен |
|------|-------------|
| `.env.example` | Шаблон — какие переменные нужны (коммитится в git) |
| `.env.development` | Переменные для `npm run dev` (локальный API) |
| `.env.production` | Переменные для `npm run build` (production API) |

**Важно:** Vite использует переменные с префиксом `VITE_`:
```
VITE_API_URL=https://eatfit24.ru/api/v1
VITE_DEBUG_MODE=false
```

---

## Папка `src/components/` — UI-компоненты

| Компонент | Что делает |
|-----------|------------|
| `Layout.tsx` | Общая обёртка страниц (header, навигация) |
| `ClientLayout.tsx` | Layout для клиентской части |
| `Dashboard.tsx` | Виджет дашборда с КБЖУ |
| `Calendar.tsx` | Календарь выбора даты |
| `MacroChart.tsx` | График макронутриентов (Chart.js) |
| `Avatar.tsx` | Аватар пользователя |
| `Toast.tsx` | Всплывающие уведомления |
| `Skeleton.tsx` | Скелетон-загрузка |
| `PullToRefresh.tsx` | Pull-to-refresh для мобильных |
| `BatchResultsModal.tsx` | Модалка результатов AI-распознавания |
| `ProfileEditModal.tsx` | Модалка редактирования профиля |
| `AuthErrorModal.tsx` | Модалка ошибки авторизации |
| `ErrorBoundary.tsx` | Обработчик ошибок React |
| `OfflineIndicator.tsx` | Индикатор офлайн-режима |
| `BrowserDebugBanner.tsx` | Баннер debug-режима в браузере |
| `PageHeader.tsx` | Заголовок страницы |
| `PlanCard.tsx` | Карточка тарифного плана |

---

## Папка `src/pages/` — Страницы

| Страница | URL | Что делает |
|----------|-----|------------|
| `ClientDashboard.tsx` | `/client` | Главная клиента: КБЖУ за день, приёмы пищи |
| `FoodLogPage.tsx` | `/client/food-log` | Добавление еды: фото → AI → сохранение |
| `MealDetailsPage.tsx` | `/client/meal/:id` | Детали приёма пищи |
| `ProfilePage.tsx` | `/client/profile` | Профиль пользователя |
| `SettingsPage.tsx` | `/client/settings` | Настройки приложения |
| `SubscriptionPage.tsx` | `/client/subscription` | Управление подпиской |
| `SubscriptionDetailsPage.tsx` | `/client/subscription/:id` | Детали подписки |
| `PaymentHistoryPage.tsx` | `/client/payments` | История платежей |
| `ApplicationsPage.tsx` | `/trainer/applications` | Заявки (для тренера) |
| `ClientsPage.tsx` | `/trainer/clients` | Список клиентов (для тренера) |
| `SubscribersPage.tsx` | `/trainer/subscribers` | Подписчики (для тренера) |
| `InviteClientPage.tsx` | `/trainer/invite` | Приглашение клиента |

---

## Папка `src/services/` — API

Здесь лежат функции для запросов к бэкенду:

```typescript
// Пример из api.ts
api.getMeals(date)           // GET /api/v1/meals/?date=2025-12-07
api.createMeal(data)         // POST /api/v1/meals/
api.recognizeFood(image)     // POST /api/v1/ai/recognize/
api.getProfile()             // GET /api/v1/profile/
api.updateProfile(data)      // PATCH /api/v1/profile/
```

---

## Папка `src/hooks/` — Кастомные хуки

| Хук | Что делает |
|-----|------------|
| `useProfile.ts` | Загрузка и обновление профиля |
| `useMeals.ts` | Работа с приёмами пищи |
| `useGoals.ts` | Цели КБЖУ |
| `useTelegram.ts` | Интеграция с Telegram WebApp |
| `useDebounce.ts` | Debounce для инпутов |

---

## Папка `src/contexts/` — Глобальное состояние

| Контекст | Что хранит |
|----------|------------|
| `AuthContext.tsx` | Данные пользователя, токен, авторизация |
| `ThemeContext.tsx` | Тема (светлая/тёмная) |

---

## Папка `public/` — Статика

```
public/
├── landing/        # HTML-страницы лендинга
├── landingcss/     # CSS для лендинга
├── landingimages/  # Картинки лендинга
└── vite.svg        # Иконка Vite
```

**Важно:** Файлы из `public/` копируются в билд как есть, без обработки.

---

## Как всё работает вместе

```
1. npm run dev
   └── Vite читает vite.config.js
       └── Запускает dev-сервер на localhost:5173
           └── Использует .env.development для переменных
               └── Проксирует /api/* на бэкенд

2. npm run build
   └── Vite читает vite.config.js
       └── Компилирует TypeScript, обрабатывает CSS
           └── Использует .env.production для переменных
               └── Создаёт dist/ с готовыми файлами

3. Docker build
   └── Читает Dockerfile
       └── npm ci → npm run build → копирует dist/ в nginx
           └── nginx.conf настраивает роутинг
```

---

## Полезные команды

```bash
# Разработка
npm run dev          # Запустить dev-сервер (localhost:5173)

# Сборка
npm run build        # Собрать production-билд в dist/
npm run preview      # Превью собранного билда

# Проверка кода
npm run lint         # Проверить код ESLint
npm run type-check   # Проверить TypeScript типы

# Тесты
npm test             # Запустить тесты
```
