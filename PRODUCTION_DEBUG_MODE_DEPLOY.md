# Production Debug Mode - Инструкция по развертыванию

## Цель

Включить Browser Debug Mode на продакшене (https://eatfit24.ru), чтобы можно было открыть миниап в обычном браузере с параметром `?web_debug=1` для отладки без Telegram.

## Что уже сделано в коде

### Frontend
✅ [frontend/.env.production:14](frontend/.env.production#L14) - `VITE_WEB_DEBUG_ENABLED=true` уже установлено
✅ [frontend/nginx.conf:33-42](frontend/nginx.conf#L33-L42) - добавлены Debug Mode заголовки в Nginx
✅ [frontend/nginx.conf:85](frontend/nginx.conf#L85) - разрешен iframe для Telegram Web (CSP)
✅ Все компоненты поддерживают Browser Debug Mode (см. BROWSER_DEBUG_MODE.md)

### Backend
✅ [backend/config/settings/base.py:40](backend/config/settings/base.py#L40) - `DEBUG_MODE_ENABLED` конфигурация
✅ [backend/apps/telegram/authentication.py:22-95](backend/apps/telegram/authentication.py#L22-L95) - `DebugModeAuthentication` реализован
✅ Логирование в AI endpoints работает ([backend/apps/ai/views.py:112](backend/apps/ai/views.py#L112), [475](backend/apps/ai/views.py#L475))

## Шаги деплоя на прод

### 1. Backend: включить DEBUG_MODE_ENABLED

На сервере 85.198.81.133 выполните:

```bash
# SSH на прод сервер
ssh root@85.198.81.133

# Перейти в директорию проекта
cd /opt/foodmind

# Отредактировать .env файл
nano .env

# Добавить или изменить строку:
DEBUG_MODE_ENABLED=true

# Сохранить (Ctrl+O, Enter, Ctrl+X)
```

**Важно:** Если в `.env` есть `DEBUG=False`, это нормально - `DEBUG_MODE_ENABLED` работает независимо.

### 2. Frontend: пересобрать и задеплоить

**На локальной машине:**

```bash
cd d:\NICOLAS\1_PROJECTS\_IT_Projects\Fitness-app

# Пересобрать frontend с обновленным nginx.conf
cd frontend
npm run build

# Вернуться в корень проекта
cd ..
```

**Передеплоить frontend на прод:**

```bash
# Остановить контейнер frontend
ssh root@85.198.81.133 "cd /opt/foodmind && docker-compose stop frontend"

# Скопировать обновленный nginx.conf на прод
scp frontend/nginx.conf root@85.198.81.133:/opt/foodmind/frontend/nginx.conf

# Скопировать пересобранную статику
scp -r frontend/dist/* root@85.198.81.133:/opt/foodmind/frontend/dist/

# Пересобрать и запустить frontend контейнер с новым nginx.conf
ssh root@85.198.81.133 "cd /opt/foodmind && docker-compose build frontend && docker-compose up -d frontend"
```

**Альтернативный метод (если используется только Docker build):**

```bash
# На проде
ssh root@85.198.81.133
cd /opt/foodmind

# Остановить и пересобрать frontend
docker-compose stop frontend
docker-compose build frontend
docker-compose up -d frontend
```

### 3. Backend: перезапустить контейнеры

```bash
ssh root@85.198.81.133
cd /opt/foodmind

# Перезапустить backend и celery для подхвата DEBUG_MODE_ENABLED
docker-compose restart backend celery-worker

# Проверить логи
docker logs fm-backend -n 50 | grep -i "debug_mode\|settings"
docker logs fm-celery-worker -n 50
```

### 4. Проверка работоспособности

#### 4.1. Проверка в браузере

Откройте в Chrome/Edge/Firefox (без Telegram):

```
https://eatfit24.ru/app?web_debug=1
```

**Ожидаемый результат:**
- ✅ Приложение открылось (НЕТ заглушки "Откройте через Telegram")
- ✅ Вверху отображается красный баннер: `⚠️ BROWSER DEBUG MODE • USER: eatfit24_debug • ID: 999999999`
- ✅ Приложение работает: можно открыть профиль, дневник, загрузить фото

#### 4.2. Проверка в DevTools

Откройте DevTools (F12) → вкладка **Network**:

1. Выполните любое действие (загрузка дневника, профиль)
2. Найдите запрос к API (например, `/api/v1/meals/` или `/api/v1/profile/`)
3. Проверьте **Request Headers**:

```
X-Debug-Mode: true
X-Debug-User-Id: 999999999
X-Telegram-ID: 999999999
X-Telegram-First-Name: Debug
X-Telegram-Username: eatfit24_debug
```

4. Проверьте, что запросы возвращают **200 OK** (не 401/403)

#### 4.3. Проверка в backend логах

```bash
ssh root@85.198.81.133

# Проверить, что создается debug-пользователь
docker logs fm-backend -n 200 | grep -i "DebugModeAuth"

# Должно быть:
# [DebugModeAuth] Debug user authenticated: user_id=... telegram_id=999999999 username=eatfit24_debug
```

#### 4.4. Проверка базы данных (опционально)

```bash
ssh root@85.198.81.133
docker exec fm-db psql -U foodmind -d foodmind -c "SELECT id, telegram_id, username, first_name FROM telegram_telegramuser WHERE telegram_id = 999999999;"

# Должна быть запись с eatfit24_debug
```

### 5. Тестирование "Еда не распознана" бага

Теперь можно отладить баг:

1. Откройте `https://eatfit24.ru/app/log?web_debug=1`
2. Загрузите фото еды
3. Откройте DevTools → **Network**:
   - Найдите запрос `/api/v1/ai/recognize/`
   - Проверьте ответ: `task_id`, `state`, `meal_id`
   - Найдите запросы `/api/v1/ai/task/{task_id}/`
   - Проверьте финальный `result.recognized_items[]`
4. Откройте DevTools → **Console**:
   - Найдите ошибки или логи, связанные с "Еда не распознана"

### 6. Проверка логов AI/Celery

```bash
ssh root@85.198.81.133

# Backend AI логи
docker logs fm-backend -n 200 | grep -E "AI recognition|TaskStatusView"

# Celery worker логи
docker logs fm-celery-worker -n 200 | grep -E "recognize_and_save_meal|task"
```

## Дополнительно: Telegram Web поддержка

После деплоя можно также дебажить через Telegram Web + DevTools:

1. Откройте https://web.telegram.org
2. Запустите миниап: https://web.telegram.org/k/#?tgaddr=tg://resolve?domain=Fit_Coach_bot&appname=app
3. Откройте DevTools (F12) прямо в Telegram Web
4. Миниап не будет блокироваться iframe благодаря [frontend/nginx.conf:85](frontend/nginx.conf#L85)

## Как отключить Debug Mode после расследования

### Вариант 1: Полное отключение

```bash
# 1. На проде отключить DEBUG_MODE_ENABLED
ssh root@85.198.81.133
cd /opt/foodmind
nano .env
# Изменить: DEBUG_MODE_ENABLED=false
docker-compose restart backend celery-worker

# 2. На локальной машине изменить .env.production
# frontend/.env.production:
# VITE_WEB_DEBUG_ENABLED=false

# 3. Пересобрать и задеплоить frontend (см. шаг 2)
```

### Вариант 2: Оставить поддержку, но требовать явного включения

Можно оставить код как есть, но просто не использовать `?web_debug=1` в URL. Без этого параметра обычные пользователи по-прежнему будут видеть заглушку "Откройте через Telegram".

## Безопасность

- ✅ Debug Mode работает **только** с параметром `?web_debug=1` в URL
- ✅ Обычные пользователи не затронуты (видят заглушку)
- ✅ Debug-пользователь (ID 999999999) создается отдельно, не влияет на prod-пользователей
- ⚠️ На production рекомендуется отключить `DEBUG_MODE_ENABLED` после расследования бага
- ⚠️ `VITE_WEB_DEBUG_ENABLED=true` в production-сборке означает, что любой может использовать `?web_debug=1` - после отладки **обязательно** вернуть в `false`

## Файлы, измененные для деплоя

1. ✅ [frontend/nginx.conf:33-42](frontend/nginx.conf#L33-L42) - Debug Mode заголовки
2. ✅ [frontend/nginx.conf:85](frontend/nginx.conf#L85) - CSP для Telegram Web
3. 🔧 `/opt/foodmind/.env` на проде - нужно добавить `DEBUG_MODE_ENABLED=true`

## Troubleshooting

### Проблема: "Откройте через Telegram" всё равно показывается

**Решение:**
- Убедитесь, что в URL есть `?web_debug=1`
- Проверьте, что frontend пересобран с `VITE_WEB_DEBUG_ENABLED=true`
- Очистите кеш браузера (Ctrl+Shift+R)

### Проблема: Backend возвращает 401/403

**Решение:**
- Проверьте, что `DEBUG_MODE_ENABLED=true` в `/opt/foodmind/.env`
- Перезапустите backend: `docker-compose restart backend`
- Проверьте логи: `docker logs fm-backend -n 100 | grep DebugMode`

### Проблема: Красный баннер не отображается

**Решение:**
- Проверьте Console в DevTools на наличие ошибок
- Убедитесь, что фронтенд пересобран и задеплоен
- Проверьте, что `isBrowserDebug` флаг установлен в AuthContext

### Проблема: CORS ошибки

**Решение:**
- Проверьте, что nginx.conf обновлен на проде
- Перезапустите frontend: `docker-compose restart frontend`
- Проверьте заголовки в Network tab DevTools

---

**Автор:** Claude Code
**Дата:** 2025-12-07
**Версия:** 1.0
