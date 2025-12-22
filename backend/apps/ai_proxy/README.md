# AI Proxy (apps/ai_proxy)

Этот модуль — “мост” между Django backend и внутренним сервисом **AI Proxy**, который распознаёт еду на фото.

## Зачем он нужен

AI Proxy позволяет:

1) **Спрятать ключи провайдеров** (OpenRouter и т.п.) — они живут только в AI Proxy  
2) **Централизовать вызовы** (логирование, метрики, лимиты, единый формат)  
3) **Изолировать доступ** — AI Proxy доступен только внутри инфраструктуры (например, через Tailscale)

---

## Главное правило (P0)

**Django HTTP-ручки НЕ ждут распознавание.**  
Долгая работа выполняется **только в Celery**.

Почему:
- иначе один запрос будет держать gunicorn worker секунды/минуты → очередь → деградация → DoS по воркерам.

---

## Как устроен поток данных

Client (MiniApp/Web)
-> Django API (/api/v1/ai/recognize/)
-> создаём Meal
-> ставим Celery task
-> отдаём 202 + task_id
-> Client polling (/api/v1/ai/task/<task_id>/)
-> SUCCESS -> отдаём результат

yaml
Копировать код

А внутри Celery:

Celery task (apps.ai.tasks)
-> AIProxyService (apps.ai_proxy.service)
-> AIProxyClient (apps.ai_proxy.client) [HTTP запрос]
-> adapter.normalize_proxy_response() [приведение формата]
-> compute_totals()
-> сохранить в БД: meal.items (FoodItem)

yaml
Копировать код

---

## Структура модуля

apps/ai_proxy/
├── init.py # публичные экспорты
├── client.py # HTTP клиент (таймауты, статусы, ошибки)
├── service.py # “одна кнопка” recognize_food()
├── adapter.py # нормализация ответа AI Proxy -> единый формат
├── exceptions.py # типы ошибок (auth/validation/timeout/server)
├── utils.py # простые утилиты (join_url, safe_json_loads и т.д.)
└── README.md # этот файл

yaml
Копировать код

---

## Настройка (ENV)

Нужно 2 переменные окружения:

```bash
AI_PROXY_URL=http://100.84.210.65:8001
AI_PROXY_SECRET=your-secret-here
Где используются
AI_PROXY_URL — базовый URL AI Proxy

AI_PROXY_SECRET — секрет для авторизации Django → AI Proxy

Таймауты (P0)
В AIProxyClient используются таймауты:

connect_timeout: 5s

read_timeout: 35s

Итого: примерно до 40 секунд.

Почему так:

долгие ответы AI должны происходить не в sync HTTP, а в фоне (Celery)

130 секунд — плохая идея: даёт зависание и убивает пропускную способность

Авторизация
Django → AI Proxy передаёт секрет в заголовке:

Authorization: Bearer <AI_PROXY_SECRET>

Важно: секрет никогда не логируем.

Публичное API модуля
1) AIProxyService (рекомендуется)
python
Копировать код
from apps.ai_proxy import AIProxyService

service = AIProxyService()

result = service.recognize_food(
    image_bytes=b"...",
    content_type="image/jpeg",
    user_comment="Курица с рисом",
    locale="ru",
    request_id="abc123",
)

print(result.items)   # список нормализованных items
print(result.totals)  # суммарные КБЖУ
print(result.meta)    # мета-информация (request_id, модель и т.д.)
Формат items (нормализованный)
json
Копировать код
{
  "items": [
    {
      "name": "Курица",
      "grams": 150,
      "calories": 250.0,
      "protein": 35.0,
      "fat": 8.0,
      "carbohydrates": 0.0,
      "confidence": 0.92
    }
  ]
}
Гарантии:

grams >= 1

числа не None

алиасы приводятся: kcal -> calories, carbs -> carbohydrates

Ошибки (исключения)
AIProxyValidationError — неправильные данные (не ретраим)

AIProxyAuthenticationError — секрет/доступ (не ретраим)

AIProxyTimeoutError — таймаут (ретраим)

AIProxyServerError — 5xx/сеть/неожиданный ответ (ретраим)

Что НЕ использовать
Не ставить большие таймауты типа 120–130 секунд

Не вызывать AI Proxy из sync HTTP-ручек в проде

Не хранить ключи провайдеров в Django

Troubleshooting
“AI_PROXY_URL не задан”
Проверь env и настройки config/settings/*.py.

“unauthorized/forbidden”
Проверь AI_PROXY_SECRET.

“timeout”
AI Proxy реально жив?

есть доступ по сети (Tailscale/Firewall)?

AI Proxy не перегружен?

См. также
apps/ai/tasks.py — где вызывается AIProxyService

apps/ai/views.py — async API + polling

markdown
Копировать код

---

## Что я **сразу** вижу как проблемы в твоём старом README (и мы это исправили)
- Там указаны **httpx** зависимости — в нашем коде **requests** (и нам это ок; проще)  
- Там указан заголовок `X-API-Key`, а мы сделали **Authorization Bearer** (единый стандарт)  
- Там endpoint указан `/api/v1/ai/recognize-food`, а в нашем client сейчас **`/v1/recognize`**  
  → это **надо синхронизировать** с реальным AI Proxy API.

### Чтобы не гадать: что мне нужно от тебя дальше (1 файл)
Скинь **доку/код AI Proxy сервиса** (его роуты): где у него реально endpoint распознавания.
Если не хочешь — просто скажи “endpoint такой-то”, например:
- `/api/v1/ai/recognize-food`
или
- `/v1/recognize`

И я сразу поправлю `client.py` на 100% точно.

---

Дальше по “AI” мы идём в `apps/ai_proxy/apps.py` (если он у тебя есть) **или** сразу делаем финальную скле