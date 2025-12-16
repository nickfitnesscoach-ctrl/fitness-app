# Telegram Auth & Security

| | |
|---|---|
| **Статус** | production-ready |
| **Владелец** | `apps/telegram/` |
| **Проверено** | 2024-12-16 |
| **Правило** | Меняешь код в `apps/telegram/*` → обнови docs |

> [!CAUTION]
> Это КРИТИЧЕСКИЙ документ. Ошибки в понимании этой логики могут привести к утечке данных и несанкционированному доступу.

---

## Безопасное логирование

> [!WARNING]
> Неправильное логирование = утечка токенов и персональных данных.

### ❌ Нельзя логировать

| Данные | Почему опасно |
|--------|---------------|
| `initData` целиком | Содержит hash + user данные, можно переиспользовать |
| `hash` из initData | Криптографическая подпись, позволяет подделку |
| `user` payload | Персональные данные (имя, id, username) |
| `TELEGRAM_BOT_TOKEN` | Полный контроль над ботом |
| `X-Bot-Secret` | Доступ к write-эндпоинтам |

### ✅ Можно логировать безопасно

| Данные | Пример |
|--------|--------|
| Длина initData | `len(init_data) = 512` |
| telegram_id (отдельно) | `telegram_id=123456789` |
| Путь запроса | `/api/v1/telegram/auth/` |
| IP адрес | `remote_addr=1.2.3.4` |
| Статус ответа | `status=200` или `status=403` |
| Факт события | `"initData validation successful"` |

### Пример безопасного логирования

```python
# ✅ Хорошо
logger.info("telegram_auth", extra={
    "telegram_id": user_id,
    "path": request.path,
    "status": "success",
})

# ❌ Плохо
logger.info(f"Auth with initData: {raw_init_data}")
```

---

## Как работает Telegram WebApp initData

Telegram Mini App (WebApp) передаёт на backend подписанные данные — `initData`. Это query-string, содержащий:

| Поле | Описание |
|------|----------|
| `user` | JSON с данными пользователя (id, first_name, username...) |
| `auth_date` | Unix timestamp когда данные были сгенерированы |
| `hash` | HMAC-SHA256 подпись всех данных |
| `query_id` | ID запроса (опционально) |
| `start_param` | Deep link параметр (опционально) |

### Пример initData

```
user=%7B%22id%22%3A123456789%2C%22first_name%22%3A%22John%22%7D
&auth_date=1702800000
&hash=abc123def456...
```

---

## Алгоритм проверки подписи

### Шаг 1: Парсинг

```python
parsed_data = dict(parse_qsl(raw_init_data))
received_hash = parsed_data.pop("hash")  # Извлекаем hash отдельно
```

### Шаг 2: Проверка auth_date (TTL)

```python
now = int(time.time())
auth_date = int(parsed_data["auth_date"])

# Слишком старая подпись
if now - auth_date > MAX_AGE_SECONDS:  # 24 часа по умолчанию
    return None

# Подпись из будущего — подозрительно
if auth_date > now + 60:
    return None
```

### Шаг 3: Построение data_check_string

Все поля (кроме `hash`) сортируются по ключам и объединяются:

```python
data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed_data.items()))
# Например: "auth_date=1702800000\nuser={...}"
```

### Шаг 4: Вычисление HMAC

Формула Telegram для WebApp:

```python
# 1. Вычисляем secret_key
secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)

# 2. Вычисляем hash
calculated_hash = HMAC_SHA256(key=secret_key, msg=data_check_string).hexdigest()
```

### Шаг 5: Сравнение

```python
if not hmac.compare_digest(calculated_hash, received_hash):
    return None  # Подпись не совпала
```

---

## Почему нельзя доверять frontend

> [!WARNING]
> Frontend может быть модифицирован злоумышленником. Backend ОБЯЗАН проверять все данные самостоятельно.

### Что может сделать атакующий:

1. **Подделать initData** — если backend не проверяет подпись
2. **Использовать старый initData** — если нет проверки TTL
3. **Прислать admin=true** — если admin-статус приходит с фронта
4. **Replay attack** — повторное использование перехваченных данных

### Backend защита:

| Атака | Защита |
|-------|--------|
| Подделка initData | HMAC проверка подписи |
| Старые данные | TTL проверка (24 часа) |
| Фейковый admin | Проверка `TELEGRAM_ADMINS` на сервере |
| Replay | auth_date + время жизни сессии |

---

## Debug Mode

### Что это

Debug Mode позволяет разрабатывать frontend без реального Telegram:

```
X-Debug-Mode: true
X-Debug-User-Id: 999999999  # опционально
```

### Как включается

```python
def _is_dev_debug_allowed() -> bool:
    # ТОЛЬКО если DEBUG=True
    if not settings.DEBUG:
        return False
    return settings.WEBAPP_DEBUG_MODE_ENABLED  # default: True
```

### Почему это опасно в PROD

> [!CAUTION]
> Debug Mode в production = **полный bypass безопасности**. Любой может представиться любым пользователем.

**Защита:**
- `DEBUG=False` в production → Debug Mode **выключен железно**
- Попытка использовать Debug Mode в PROD → 401 Unauthorized

---

## Определение admin-доступа

### TELEGRAM_ADMINS

В `settings.py` задаётся список Telegram ID администраторов:

```python
TELEGRAM_ADMINS = [123456789, 987654321]
# или
TELEGRAM_ADMINS = "123456789,987654321"
# или
TELEGRAM_ADMINS = 123456789  # если один
```

### Проверка

```python
def _is_telegram_admin(request) -> bool:
    # 1. Есть initData?
    raw_init_data = request.headers.get("X-Telegram-Init-Data")
    if not raw_init_data:
        return False
    
    # 2. initData валиден?
    parsed = auth_service.validate_init_data(raw_init_data)
    if not parsed:
        return False
    
    # 3. User ID в списке админов?
    user_id = auth_service.get_user_id_from_init_data(parsed)
    admins = _parse_telegram_admins()
    
    return user_id in admins
```

### Где используется

| Компонент | Что делает |
|-----------|------------|
| `@telegram_admin_required` | Декоратор для Django views |
| `TelegramAdminPermission` | DRF permission class |
| `TelegramAdminOnlyMiddleware` | Защита Django Admin (`/dj-admin/`) |

---

## Критические прод-настройки

> [!IMPORTANT]
> Перед деплоем в production убедитесь, что эти настройки корректны.

### DEBUG

```python
# settings.py
DEBUG = False  # ОБЯЗАТЕЛЬНО False в production
```

**Что отключается при `DEBUG=False`:**
- Debug Mode аутентификация
- Детальные сообщения об ошибках
- Django Debug Toolbar (если есть)

### WEBAPP_DEBUG_MODE_ENABLED

```python
WEBAPP_DEBUG_MODE_ENABLED = False  # рекомендуется явно указать False в prod
```

**Даже если `DEBUG=False`, лучше явно указать эту настройку.**

### TELEGRAM_ADMINS

```python
TELEGRAM_ADMINS = [310151740]  # реальные Telegram ID администраторов
```

**Что будет если пустой:**
- DEV: доступ разрешён (для разработки)
- PROD: `403 Forbidden` для всех

### TELEGRAM_BOT_TOKEN

```python
TELEGRAM_BOT_TOKEN = "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
```

**Используется для:**
- Проверки подписи initData
- НИКОГДА не логировать, не выводить в ошибки

### TELEGRAM_BOT_API_SECRET

```python
TELEGRAM_BOT_API_SECRET = "super-secret-key-for-bot-api"
```

**Используется для:**
- Авторизации запросов от бота через `X-Bot-Secret`
- Должен быть случайной строкой 32+ символов

---

## Анти-паттерны

> [!CAUTION]
> НЕ делайте следующее:

### ❌ Логирование initData

```python
# ПЛОХО: initData содержит персональные данные
logger.info(f"initData: {raw_init_data}")
```

```python
# ХОРОШО: логируем только факт, без данных
logger.info("initData validation successful")
```

### ❌ Открытые write-эндпоинты

```python
# ПЛОХО: AllowAny без проверки секрета
@api_view(["POST"])
@permission_classes([AllowAny])
def create_something(request):
    ...  # любой может вызвать
```

```python
# ХОРОШО: проверяем X-Bot-Secret
@api_view(["POST"])
@permission_classes([AllowAny])
def create_something(request):
    if not _bot_secret_ok(request):
        return _forbidden()
    ...
```

### ❌ Admin-флаг с frontend

```python
# ПЛОХО: доверяем фронту
is_admin = request.data.get("is_admin")
```

```python
# ХОРОШО: проверяем на сервере
is_admin = telegram_user.telegram_id in admin_ids
```

### ❌ Сравнение hash через ==

```python
# ПЛОХО: уязвимо к timing attack
if calculated_hash == received_hash:
    ...
```

```python
# ХОРОШО: constant-time сравнение
if hmac.compare_digest(calculated_hash, received_hash):
    ...
```

### ❌ Отсутствие TTL проверки

```python
# ПЛОХО: старый initData всё ещё действителен
parsed = parse_init_data(raw)
if verify_hash(parsed):
    return parsed  # а если ему год?
```

```python
# ХОРОШО: проверяем auth_date
if not check_ttl(parsed["auth_date"], max_age=86400):
    return None
```

---

## Чек-лист безопасности

Перед деплоем проверьте:

| # | Проверка | Как проверить |
|---|----------|---------------|
| 1 | `DEBUG=False` | `python manage.py shell -c "from django.conf import settings; print(settings.DEBUG)"` |
| 2 | `TELEGRAM_ADMINS` заполнен | Проверить `.env` или `settings.py` |
| 3 | `TELEGRAM_BOT_TOKEN` установлен | Проверить `.env` |
| 4 | `TELEGRAM_BOT_API_SECRET` установлен | Проверить `.env` |
| 5 | Bot API недоступен без секрета | `curl -X POST /api/v1/telegram/save-test/` → 403 |
| 6 | Trainer Panel недоступен без initData | `curl /api/v1/telegram/applications/` → 403 |
| 7 | initData не логируется | Проверить логи после авторизации |

---

## Схема аутентификации

```
┌─────────────────────────────────────────────────────────────────┐
│                     Telegram Mini App                            │
│                                                                  │
│  window.Telegram.WebApp.initData                                 │
│       │                                                          │
│       ▼                                                          │
│  X-Telegram-Init-Data: <initData>                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Backend                                   │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐     │
│  │            TelegramWebAppAuthentication                 │     │
│  │                                                         │     │
│  │  1. Извлечь initData из заголовка                      │     │
│  │  2. Распарсить query-string                            │     │
│  │  3. Проверить TTL (auth_date)                          │     │
│  │  4. Построить data_check_string                        │     │
│  │  5. Вычислить HMAC                                     │     │
│  │  6. Сравнить с hash (constant-time)                    │     │
│  │  7. Извлечь user данные                                │     │
│  │  8. Найти/создать Django User                          │     │
│  │  9. Найти/создать TelegramUser                         │     │
│  │  10. Вернуть (user, auth_info)                         │     │
│  └────────────────────────────────────────────────────────┘     │
│                              │                                   │
│                              ▼                                   │
│                      DRF View / JWT                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```
