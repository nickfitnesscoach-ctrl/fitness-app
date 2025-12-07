# Production Debug Mode - Чеклист проверки

После деплоя используйте этот чеклист для проверки работоспособности.

## Pre-Deploy Checklist

- [ ] `VITE_WEB_DEBUG_ENABLED=true` в [frontend/.env.production](frontend/.env.production)
- [ ] Debug Mode заголовки добавлены в [frontend/nginx.conf](frontend/nginx.conf)
- [ ] CSP для Telegram Web настроен в [frontend/nginx.conf](frontend/nginx.conf)
- [ ] `DEBUG_MODE_ENABLED=true` добавлен в `/opt/foodmind/.env` на проде

## Deploy Checklist

- [ ] Frontend пересобран (`npm run build`)
- [ ] `nginx.conf` скопирован на прод
- [ ] `dist/` скопирован на прод
- [ ] Frontend контейнер пересобран и перезапущен
- [ ] Backend и Celery перезапущены

## Post-Deploy Verification

### 1. Браузерная проверка

- [ ] Открыть https://eatfit24.ru/app?web_debug=1 (без Telegram)
- [ ] Вижу красный баннер: `⚠️ BROWSER DEBUG MODE • USER: eatfit24_debug • ID: 999999999`
- [ ] НЕТ заглушки "Откройте через Telegram"
- [ ] Приложение загружается и работает

### 2. DevTools Network проверка

Откройте DevTools (F12) → Network:

- [ ] Выполнить действие (загрузка дневника, профиль)
- [ ] Найти запрос к API (например `/api/v1/meals/`)
- [ ] Request Headers содержат:
  - `X-Debug-Mode: true`
  - `X-Debug-User-Id: 999999999`
  - `X-Telegram-ID: 999999999`
  - `X-Telegram-Username: eatfit24_debug`
- [ ] Response Status: **200 OK** (НЕ 401/403)

### 3. Backend логи

```bash
ssh root@85.198.81.133
docker logs fm-backend -n 100 | grep -i DebugMode
```

Ожидаемый вывод:
- [ ] `[DebugModeAuth] Debug user authenticated: user_id=... telegram_id=999999999 username=eatfit24_debug`

### 4. База данных (опционально)

```bash
ssh root@85.198.81.133
docker exec fm-db psql -U foodmind -d foodmind -c \
  "SELECT id, telegram_id, username, first_name FROM telegram_telegramuser WHERE telegram_id = 999999999;"
```

- [ ] Найдена запись с `telegram_id=999999999` и `username=eatfit24_debug`

### 5. Функциональная проверка

В браузере с `?web_debug=1`:

#### Профиль
- [ ] Открыть https://eatfit24.ru/app/profile?web_debug=1
- [ ] Профиль загружается
- [ ] Можно редактировать данные

#### Дневник питания
- [ ] Открыть https://eatfit24.ru/app?web_debug=1&date=2025-12-07
- [ ] Дневник отображается
- [ ] Можно добавлять еду вручную

#### Загрузка фото (AI)
- [ ] Открыть https://eatfit24.ru/app/log?web_debug=1
- [ ] Выбрать фото еды
- [ ] Проверить в Network:
  - Запрос `/api/v1/ai/recognize/` отправлен
  - Получен ответ с `task_id` и `meal_id`
  - Запросы `/api/v1/ai/task/{task_id}/` выполняются
  - Статус задачи меняется: `PENDING` → `STARTED` → `SUCCESS`
- [ ] В Console нет ошибок CORS/401/403

### 6. Telegram Web проверка (опционально)

- [ ] Открыть https://web.telegram.org
- [ ] Запустить миниап через бота
- [ ] Миниап загружается (НЕТ ошибок iframe/CSP)
- [ ] DevTools можно открыть прямо в Telegram Web

## Debug "Еда не распознана" Bug

После успешного деплоя можно отладить баг:

### Frontend проверка

1. [ ] Открыть https://eatfit24.ru/app/log?web_debug=1
2. [ ] Загрузить фото, которое вызывает "Еда не распознана"
3. [ ] DevTools → Console:
   - [ ] Найти ошибки/логи, связанные с "Еда не распознана"
   - [ ] Проверить, в каком компоненте/хуке возникает ошибка
4. [ ] DevTools → Network:
   - [ ] Проверить ответ `/api/v1/ai/task/{task_id}/`
   - [ ] Проверить `result.recognized_items` - пустой или есть данные?
   - [ ] Проверить `state` - `SUCCESS` или `FAILURE`?

### Backend логи

```bash
ssh root@85.198.81.133

# AI recognition логи
docker logs fm-backend -n 300 | grep -E "AI recognition|recognize_and_save_meal"

# Task status логи
docker logs fm-backend -n 300 | grep -E "Task.*status|TaskStatusView"

# Celery worker логи
docker logs fm-celery-worker -n 300 | grep -E "recognize_and_save_meal|task"
```

Что искать:
- [ ] Успешное распознавание: `recognized_items` не пустой
- [ ] Ошибки AI Proxy: `AIProxyError`, `AIProxyTimeoutError`
- [ ] Ошибки парсинга JSON: `JSON parsing failed`

## Rollback (если что-то пошло не так)

Если Debug Mode вызывает проблемы у обычных пользователей:

```bash
# 1. Отключить DEBUG_MODE_ENABLED
ssh root@85.198.81.133
cd /opt/foodmind
nano .env
# Изменить: DEBUG_MODE_ENABLED=false
docker-compose restart backend celery-worker

# 2. (Опционально) Вернуть старый nginx.conf
# Если нужно полностью откатить Nginx изменения
```

Обычные пользователи НЕ затронуты, если не используют `?web_debug=1`.

## Отключение после отладки

После расследования бага:

1. [ ] На проде: `DEBUG_MODE_ENABLED=false` в `.env`
2. [ ] Локально: `VITE_WEB_DEBUG_ENABLED=false` в `frontend/.env.production`
3. [ ] Пересобрать и задеплоить frontend (повторить Deploy Checklist)
4. [ ] Перезапустить backend: `docker-compose restart backend celery-worker`

---

**Документация:**
- Подробная инструкция: [PRODUCTION_DEBUG_MODE_DEPLOY.md](PRODUCTION_DEBUG_MODE_DEPLOY.md)
- Quick deploy скрипт: [QUICK_DEBUG_DEPLOY.sh](QUICK_DEBUG_DEPLOY.sh)
- Browser Debug Mode описание: [BROWSER_DEBUG_MODE.md](BROWSER_DEBUG_MODE.md)

**Автор:** Claude Code
**Дата:** 2025-12-07
