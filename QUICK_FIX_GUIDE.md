# Quick Fix Guide — FoodMind
## Немедленные действия для запуска проекта

### Обнаружены критические баги:

**❌ Проблема 1:** Backend использовал SQLite вместо PostgreSQL
**❌ Проблема 2:** Бот не отправлял данные в backend (DJANGO_API_URL не настроен)
**❌ Результат:** Панель тренера не видит заявок и клиентов

---

## ✅ Исправления (уже применены)

### 1. backend/.env

**Изменено:**
```diff
- DATABASE_URL=sqlite:///db.sqlite3
+ DATABASE_URL=postgresql://foodmind:foodmind@localhost:5432/foodmind

+ # Telegram Admins (comma-separated Telegram IDs)
+ TELEGRAM_ADMINS=310151740
+ BOT_ADMIN_ID=310151740
```

**Файл:** [backend/.env](backend/.env:9)

---

### 2. bot/.env.example

**Изменено:**
```diff
# Database
- DB_NAME=foodmind_bot_db
+ DB_NAME=foodmind  # Та же БД что у backend!

# Django API Integration
- DJANGO_API_URL=http://localhost:8000/api/v1
+ DJANGO_API_URL=http://backend:8000/api/v1  # Для Docker
```

**Файл:** [bot/.env.example](bot/.env.example:12)

---

## 🚀 Как запустить проект

### Вариант 1: Docker Compose (Production/Staging)

```bash
# 1. Создать .env в корне проекта (если нет)
cp .env.example .env

# 2. Заполнить обязательные переменные:
# - POSTGRES_PASSWORD
# - TELEGRAM_BOT_TOKEN
# - OPENROUTER_API_KEY

# 3. Запустить все сервисы
docker-compose up -d

# 4. Проверить статус
docker-compose ps

# 5. Применить миграции (первый запуск)
docker exec fm-backend python manage.py migrate
docker exec fm-bot alembic upgrade head

# 6. Создать суперпользователя Django (опционально)
docker exec -it fm-backend python manage.py createsuperuser
```

**Проверка:**
```bash
# Backend health
curl http://localhost:8000/health/

# Frontend
curl http://localhost:3000/

# Bot logs
docker logs fm-bot | tail -20
```

---

### Вариант 2: Локальная разработка (Development)

```bash
# 1. Запустить PostgreSQL через Docker
docker-compose up -d db

# 2. Настроить backend/.env
# DATABASE_URL=postgresql://foodmind:foodmind@localhost:5432/foodmind

# 3. Применить миграции
cd backend
python manage.py migrate
python manage.py createsuperuser

# 4. Запустить backend (терминал 1)
python manage.py runserver

# 5. Настроить bot/.env (создать на основе .env.example)
cd ../bot
cp .env.example .env
# Заполнить DJANGO_API_URL=http://localhost:8000/api/v1

# 6. Применить миграции бота
alembic upgrade head

# 7. Запустить бота (терминал 2)
python main.py

# 8. Запустить frontend (терминал 3)
cd ../frontend
npm install
npm run dev
```

---

## 🧪 Тестовые сценарии

### Сценарий 1: Проверка заявок в панели тренера

```
1. Открыть бота в Telegram
2. Нажать /personal_plan
3. Пройти AI тест (пол, возраст, вес, рост, цели)
4. Дождаться генерации плана
5. Открыть панель тренера (Telegram WebApp)
6. Перейти во вкладку "Заявки"

✅ Ожидаемый результат:
- Заявка отображается в списке
- Видны: имя, дата, возраст, вес, рост, цели
- Рекомендованные КБЖУ рассчитаны
```

**Диагностика (если не работает):**
```bash
# Проверить, что бот отправил данные в Django
docker logs fm-bot | grep "Test results saved to Django"

# Проверить данные в БД
docker exec fm-db psql -U foodmind -d foodmind -c \
  "SELECT id, telegram_id, first_name, ai_test_completed FROM telegram_telegramuser;"
```

---

### Сценарий 2: Добавление приёма пищи

```
1. Открыть клиентский миниапп (Telegram WebApp)
2. На главной странице нажать "Добавить приём пищи"
3. Выбрать фото из галереи ИЛИ сделать фото камерой
4. Дождаться анализа AI (10-30 сек)
5. Подтвердить распознанные блюда
6. Нажать "Сохранить"

✅ Ожидаемый результат:
- Приём пищи появляется на главной в блоке "Сегодня"
- Калории и КБЖУ обновляются
```

**Примечание:**
Камера работает только в Telegram WebApp (не в браузере).

---

## 🔍 Диагностика проблем

### Проблема: "Заявки не отображаются"

**Возможные причины:**
1. Бот не отправляет данные в backend → проверить `DJANGO_API_URL`
2. Backend использует SQLite → проверить `backend/.env:DATABASE_URL`
3. Миграции не применены → `docker exec fm-backend python manage.py showmigrations`

**Решение:**
```bash
# 1. Проверить переменную DJANGO_API_URL
docker exec fm-bot env | grep DJANGO_API_URL

# 2. Проверить, что backend доступен
docker exec fm-bot curl http://backend:8000/health/

# 3. Проверить таблицу TelegramUser
docker exec fm-db psql -U foodmind -d foodmind -c \
  "SELECT COUNT(*) FROM telegram_telegramuser WHERE ai_test_completed=true;"
```

---

### Проблема: "Не работает добавление приёма пищи"

**Возможные причины:**
1. AI API не настроен → проверить `OPENROUTER_API_KEY`
2. Фронтенд не может подключиться к backend → проверить CORS

**Решение:**
```bash
# 1. Проверить OPENROUTER_API_KEY
docker exec fm-backend env | grep OPENROUTER_API_KEY

# 2. Проверить CORS настройки
docker exec fm-backend python manage.py shell
>>> from django.conf import settings
>>> print(settings.CORS_ALLOWED_ORIGINS)

# 3. Проверить логи backend
docker logs fm-backend | grep "POST /api/v1/ai/recognize"
```

---

## 📊 Проверка данных в БД

### Прямой доступ к PostgreSQL

```bash
# Подключиться к БД
docker exec -it fm-db psql -U foodmind -d foodmind

# Посмотреть таблицы
\dt

# Количество пользователей Telegram
SELECT COUNT(*) FROM telegram_telegramuser;

# Количество заявок (прошедших тест)
SELECT COUNT(*) FROM telegram_telegramuser WHERE ai_test_completed=true;

# Количество клиентов
SELECT COUNT(*) FROM telegram_telegramuser WHERE is_client=true;

# Последние 5 заявок
SELECT id, telegram_id, first_name, created_at
FROM telegram_telegramuser
WHERE ai_test_completed=true
ORDER BY created_at DESC
LIMIT 5;

# Таблицы бота (SQLAlchemy)
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM survey_answers;
SELECT COUNT(*) FROM plans;
```

---

## ⚠️ Важные замечания

### 1. База данных

**До исправления:**
```
Bot → PostgreSQL (users, survey_answers, plans)
Backend → SQLite (пустая БД)
```

**После исправления:**
```
Bot → PostgreSQL (users, survey_answers, plans)
      ↓ HTTP POST /api/v1/telegram/save-test/
Backend → PostgreSQL (telegram_telegramuser, auth_user, users_profile)
```

Бот и Backend используют **один PostgreSQL instance**, но **разные таблицы**.
Синхронизация через HTTP API — это корректный дизайн.

---

### 2. Миграции

**Две системы миграций:**
- Bot: Alembic (SQLAlchemy)
- Backend: Django Migrations

**При деплое выполнить обе:**
```bash
docker exec fm-backend python manage.py migrate
docker exec fm-bot alembic upgrade head
```

---

### 3. Настройки (уведомления, язык, часовой пояс)

**Текущее состояние:**
- Часовой пояс: ✅ Сохраняется из AI теста
- Уведомления: ⚠️ UI заглушка (статический текст)
- Язык: ⚠️ UI заглушка (статический текст)

**Как работает:**
Часовой пояс сохраняется в `users_profile.timezone` при прохождении AI теста.
Остальные настройки можно добавить позже.

---

## 📝 Полный отчёт

Смотри детальный отчёт с диаграммами и архитектурными находками:
[ARCHITECTURE_AUDIT_REPORT.md](ARCHITECTURE_AUDIT_REPORT.md)

---

**Дата:** 2025-11-24
**Версия:** 1.0
**Аудитор:** Claude Code (Sonnet 4.5)
