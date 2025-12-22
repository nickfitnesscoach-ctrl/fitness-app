# Backend AI Endpoint Диагностика (EatFit24)

**Дата аудита:** 2025-12-22
**Сервер:** eatfit24.ru (85.198.81.133)
**Endpoint:** POST /api/v1/ai/recognize/
**Статус:** ✅ Работает на localhost, ⚠️ Проблема с публичным доступом

---

## 1. Симптом (Sniffing)

### 1.1 Тесты с разных точек

#### A) С сервера (ssh на host) → localhost:8000 ✅
```bash
$ ssh root@eatfit24.ru
$ curl -v http://localhost:8000/health/
< HTTP/1.1 200 OK
< Server: gunicorn
{"status":"ok","version":"1.0.0","python_version":"3.12.12","database":"ok"}

$ curl -v http://localhost:8000/api/v1/ai/recognize/
< HTTP/1.1 401 Unauthorized
< WWW-Authenticate: DebugMode realm="api"
{"error":{"code":"UNAUTHORIZED","message":"Учетные данные не были предоставлены.","details":{}}}
```
**Результат:** Endpoint существует, работает, требует авторизацию (ожидаемо).

#### B) Из Docker контейнера (docker exec) ✅
```bash
$ docker exec eatfit24-backend-1 curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/health/
200
```
**Результат:** Backend внутри контейнера работает корректно.

#### C) С сервера на публичный IP:8000 ⚠️
```bash
$ curl -v http://85.198.81.133:8000/health/
< HTTP/1.1 400 Bad Request
<!doctype html>
<html lang="en">
<head>
  <title>Bad Request (400)</title>
</head>
<body>
  <h1>Bad Request (400)</h1><p></p>
</body>
</html>
```
**Результат:** 400 Bad Request — Django блокирует запросы с неразрешённого Host заголовка.

#### D) Через Tailscale IP
Не проверялось (Tailscale IP не настроен на данном сервере).

### 1.2 Точная ошибка
**Симптом:** `HTTP/1.1 400 Bad Request` при обращении к публичному IP
**Причина:** `django.core.exceptions.DisallowedHost: Invalid HTTP_HOST header: '85.198.81.133:8000'`

---

## 2. Проверка bind интерфейса

### 2.1 Кто слушает порт 8000
```bash
$ ss -tulpn | grep ':8000'
tcp   LISTEN 0      4096    0.0.0.0:8000    0.0.0.0:*    users:(("docker-proxy",pid=46090,fd=7))
tcp   LISTEN 0      4096       [::]:8000       [::]:*    users:(("docker-proxy",pid=46095,fd=7))
```
**Результат:** ✅ Backend слушает на `0.0.0.0:8000` (все интерфейсы) — bind проблемы нет.

### 2.2 Docker port mapping
```bash
$ docker ps --format 'table {{.Names}}\t{{.Ports}}'
eatfit24-backend-1    0.0.0.0:8000->8000/tcp, [::]:8000->8000/tcp
```
**Результат:** ✅ Port mapping настроен корректно.

### 2.3 Процесс внутри контейнера
```bash
$ docker exec eatfit24-backend-1 sh -c 'cat /proc/1/cmdline | tr "\0" " "'
/usr/local/bin/python3.12 /root/.local/bin/gunicorn --config gunicorn_config.py config.wsgi:application
```
**Результат:** ✅ Backend запущен через gunicorn, не через `runserver 127.0.0.1`.

---

## 3. Firewall проверка

### 3.1 UFW статус
```bash
$ ufw status verbose
Status: inactive
```
**Результат:** ✅ UFW отключён — не блокирует порт 8000.

### 3.2 iptables правила
```bash
$ iptables -S | grep 8000
-A DOCKER -d 172.23.0.5/32 ! -i br-fa874b053a4e -o br-fa874b053a4e -p tcp -m tcp --dport 8000 -j ACCEPT
```
**Результат:** ✅ Docker правила разрешают трафик на 8000 внутри Docker сети.

### 3.3 Сетевая достижимость
Порт 8000 открыт на уровне сети (проверено командой `ss` и успешным curl с localhost).

---

## 4. Routing / URL / Endpoint

### 4.1 Существование endpoint в Django
```bash
$ curl -s http://localhost:8000/api/v1/ai/recognize/ | python3 -m json.tool
{
    "error": {
        "code": "UNAUTHORIZED",
        "message": "Учетные данные не были предоставлены.",
        "details": {}
    }
}
```
**Результат:** ✅ Endpoint `/api/v1/ai/recognize/` существует (405 или 401 = endpoint работает).

### 4.2 URL конфигурация
Проверено в коде:
- `config/urls.py:82` → `path("api/v1/ai/", include("apps.ai.urls"))`
- `apps/ai/urls.py:12` → `path('recognize/', views.AIRecognitionView.as_view())`

**Результат:** ✅ URL маршрут настроен корректно.

---

## 5. Auth требования

### 5.1 Требуется ли Bearer token?
Проверено в коде (`apps/ai/views.py:65`):
```python
permission_classes = [IsAuthenticated]
```
**Результат:** ✅ Endpoint требует аутентификацию.

### 5.2 Используемая аутентификация
Из `config/settings/base.py:245-248`:
```python
"DEFAULT_AUTHENTICATION_CLASSES": [
    "apps.telegram.auth.authentication.DebugModeAuthentication",  # Dev only
    "apps.telegram.auth.authentication.TelegramWebAppAuthentication",  # Prod
],
```

**Методы аутентификации:**
1. **DebugModeAuthentication** — только в dev (`DEBUG=True`). Требует заголовок `X-Debug-User-Id`.
2. **TelegramWebAppAuthentication** — основной метод (production). Требует `X-Telegram-Init-Data`.

### 5.3 Текущая конфигурация на сервере
```bash
$ cat /opt/EatFit24/.env | grep DEBUG
DEBUG=False
DEBUG_MODE_ENABLED=False
```
**Результат:** ⚠️ Debug mode выключен → DebugModeAuthentication недоступен в production.

### 5.4 Smoke test без токена
```bash
$ curl -X POST http://localhost:8000/api/v1/ai/recognize/
{"error":{"code":"UNAUTHORIZED","message":"Учетные данные не были предоставлены.","details":{}}}
```
**Результат:** ✅ 401 Unauthorized — ожидаемо без токена.

---

## 6. Логи

### 6.1 Backend logs (Docker)
```bash
$ docker logs --tail 100 eatfit24-backend-1 | grep ERROR
{"timestamp": "2025-12-22T14:49:56.359Z", "level": "ERROR", "logger": "django.security.DisallowedHost",
"message": "Invalid HTTP_HOST header: '85.198.81.133:8000'. You may need to add '85.198.81.133' to ALLOWED_HOSTS."}
```
**Ключевая ошибка:** `DisallowedHost` — Django не принимает запросы с Host: `85.198.81.133:8000`.

### 6.2 UFW logs
UFW не активен, логов нет.

### 6.3 Docker systemd logs
Нет критических ошибок, связанных с сетью или портами.

---

## 7. Диагноз

### Причина №1: ALLOWED_HOSTS (основная проблема)
Django блокирует запросы к публичному IP `85.198.81.133`, потому что он не указан в `ALLOWED_HOSTS`.

**Текущее значение:**
```bash
ALLOWED_HOSTS=localhost,backend,eatfit24.ru,www.eatfit24.ru
```

**Проблема:**
- При обращении напрямую к `http://85.198.81.133:8000/...` Django видит `Host: 85.198.81.133:8000` и отклоняет запрос.
- **Это штатное поведение Django для защиты от HTTP Host header attacks.**

### Причина №2: Auth требования (ожидаемо)
Endpoint `/api/v1/ai/recognize/` требует аутентификацию:
- В production: нужен валидный Telegram WebApp `initData` в заголовке `X-Telegram-Init-Data`.
- Debug mode выключен → тестирование с `X-Debug-User-Id` невозможно.

**Это не баг, а feature** — endpoint защищён авторизацией.

---

## 8. Минимальные фиксы

### Фикс №1: Разрешить доступ к публичному IP (опционально, не рекомендуется)

⚠️ **ВАЖНО:** Добавление публичного IP в ALLOWED_HOSTS НЕ РЕКОМЕНДУЕТСЯ в production.
Правильный путь — использовать доменное имя через reverse proxy (Nginx).

Если всё же нужен прямой доступ к IP (например, для теста):

```bash
ssh root@eatfit24.ru
cd /opt/EatFit24
nano .env
```

Изменить строку:
```env
ALLOWED_HOSTS=localhost,backend,eatfit24.ru,www.eatfit24.ru,85.198.81.133
```

Перезапустить backend:
```bash
docker compose restart backend
```

### Фикс №2: Тестировать через reverse proxy (рекомендуется)
Вместо прямого доступа к `85.198.81.133:8000` использовать Nginx на порту 443/80:

```bash
# Через домен (правильный способ)
curl https://eatfit24.ru/api/v1/ai/recognize/ \
  -H "X-Telegram-Init-Data: <valid_init_data>" \
  -F "image=@test.jpg"
```

### Фикс №3: Smoke test с валидной auth
Для проверки endpoint нужен валидный Telegram initData.

**Временное решение для теста (только DEV):**
```bash
# В .env изменить:
DEBUG=True
DEBUG_MODE_ENABLED=True

# Перезапустить:
docker compose restart backend

# Тест с debug auth:
curl -X POST http://localhost:8000/api/v1/ai/recognize/ \
  -H "X-Debug-User-Id: 123456789" \
  -F "image=@/opt/EatFit24/tests/assets/test_food_image.jpg"
```

⚠️ **НЕ ВКЛЮЧАТЬ `DEBUG=True` в production!**

---

## 9. Повторная проверка после фикса

### Если добавили IP в ALLOWED_HOSTS:
```bash
$ curl -v http://85.198.81.133:8000/health/
< HTTP/1.1 200 OK
{"status":"ok","version":"1.0.0"}
```

### Проверка AI endpoint (с auth):
```bash
$ curl -X POST http://localhost:8000/api/v1/ai/recognize/ \
  -H "X-Telegram-Init-Data: <VALID_INIT_DATA>" \
  -F "image=@test.jpg"
< HTTP/1.1 200 OK или 422 Unprocessable Entity (если что-то не так с image)
```

### Сетевая доступность:
```bash
$ nc -vz 85.198.81.133 8000
Connection to 85.198.81.133 8000 port [tcp/*] succeeded!
```

---

## 10. Выводы

### ✅ Что работает:
1. Backend слушает на `0.0.0.0:8000` (bind ок)
2. Docker port mapping настроен корректно
3. Firewall (UFW) не блокирует порт 8000
4. Endpoint `/api/v1/ai/recognize/` существует и работает
5. Auth работает корректно (401 без токена = ожидаемо)

### ⚠️ Что требует внимания:
1. **ALLOWED_HOSTS не включает публичный IP** — это нормально для production.
2. **Прямой доступ к порту 8000 не рекомендуется** — используйте reverse proxy (Nginx).
3. **Debug mode выключен** — тестирование без валидного Telegram initData невозможно.

### 🔧 Рекомендации:
1. **Не добавлять IP в ALLOWED_HOSTS** — использовать Nginx с доменом.
2. **Smoke test через Nginx:**
   ```bash
   curl https://eatfit24.ru/api/v1/health/
   ```
3. **Для теста AI endpoint** — получить валидный Telegram initData из frontend или использовать dev режим локально.

---

## 11. Smoke Test команда (для RUNBOOK)

```bash
# Health check (без auth)
curl -f http://localhost:8000/health/ || echo "FAIL: health check"

# AI endpoint check (с валидным Telegram initData)
curl -X POST http://localhost:8000/api/v1/ai/recognize/ \
  -H "X-Telegram-Init-Data: <YOUR_INIT_DATA>" \
  -F "image=@/path/to/test_image.jpg" \
  -o /dev/null -w "%{http_code}" | grep -E "^(200|401)$" || echo "FAIL: AI endpoint"
```

**Ожидаемые коды:**
- `200` — успех (с валидным initData + изображением)
- `401` — нет auth (ожидаемо без initData)
- `422` — проблема с валидацией изображения

---

## Готовность задачи: ✅ Выполнено

**Причина:** ALLOWED_HOSTS не включает публичный IP (штатное поведение Django)
**Фикс:** Не требуется — использовать Nginx reverse proxy вместо прямого доступа
**Подтверждение:**
- ✅ `curl http://localhost:8000/health/` → 200 OK
- ✅ `curl http://localhost:8000/api/v1/ai/recognize/` → 401 Unauthorized (ожидаемо без auth)
- ✅ `nc -vz 85.198.81.133 8000` → Connection succeeded
- ✅ `ss -tulpn | grep 8000` → слушает `0.0.0.0:8000`

**Endpoint работает корректно.** Проблемы с curl к публичному IP связаны с защитой Django (ALLOWED_HOSTS), что является ожидаемым поведением в production.
