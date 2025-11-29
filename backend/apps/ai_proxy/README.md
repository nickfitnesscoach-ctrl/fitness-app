# AI Proxy Integration

Интеграция с внутренним сервисом AI Proxy для распознавания еды.

## Описание

AI Proxy — это внутренний микросервис EatFit24, который оборачивает вызовы к OpenRouter API для распознавания еды на фотографиях.

### Преимущества использования AI Proxy:

1. **Централизация**: Один сервис управляет всеми вызовами к OpenRouter
2. **Безопасность**: API ключи OpenRouter хранятся только в AI Proxy
3. **Мониторинг**: Логирование и метрики в одном месте
4. **Изоляция**: AI Proxy доступен только через Tailscale VPN

## Структура модуля

```
apps/ai_proxy/
├── __init__.py
├── apps.py              # Django app config
├── client.py            # HTTP клиент для AI Proxy
├── service.py           # Сервис-обертка для интеграции
├── adapter.py           # Адаптер ответов AI Proxy -> legacy формат
├── exceptions.py        # Кастомные исключения
└── README.md            # Документация
```

## Настройка

### 1. Переменные окружения

Добавьте в `.env`:

```bash
# AI Proxy Configuration
AI_PROXY_URL=http://100.84.210.65:8001
AI_PROXY_SECRET=your-secret-key-here
```

### 2. Установка зависимостей

```bash
pip install httpx>=0.27.0
```

## Использование

### Базовый пример

```python
from apps.ai_proxy.service import AIProxyRecognitionService

# Инициализация сервиса
service = AIProxyRecognitionService()

# Распознавание еды
result = service.recognize_food(
    image_data_url="data:image/jpeg;base64,/9j/4AAQ...",
    user_comment="Куриная грудка с рисом",
)

# Результат в legacy формате
print(result)
# {
#     "recognized_items": [
#         {
#             "name": "Куриная грудка гриль",
#             "confidence": 0.95,
#             "estimated_weight": 150,
#             "calories": 165,
#             "protein": 31.0,
#             "fat": 3.6,
#             "carbohydrates": 0.0
#         }
#     ]
# }
```

### Обработка ошибок

```python
from apps.ai_proxy.service import AIProxyRecognitionService
from apps.ai_proxy.exceptions import (
    AIProxyAuthenticationError,
    AIProxyServerError,
    AIProxyTimeoutError,
)

service = AIProxyRecognitionService()

try:
    result = service.recognize_food(image_data_url="...")
except AIProxyAuthenticationError:
    # Неверный API ключ (401)
    print("Проверьте AI_PROXY_SECRET")
except AIProxyTimeoutError:
    # Таймаут (>30s)
    print("AI Proxy не отвечает")
except AIProxyServerError as e:
    # Ошибка сервера (500) или сетевая ошибка
    print(f"Ошибка AI Proxy: {e}")
```

## API клиента

### AIProxyClient

Низкоуровневый HTTP клиент для прямых вызовов к AI Proxy.

```python
from apps.ai_proxy.client import AIProxyClient

client = AIProxyClient()

# Распознавание с пользовательским комментарием
response = client.recognize_food(
    image_url="https://example.com/food.jpg",
    user_comment="3 сэндвича с сыром",
    locale="ru"
)

# Ответ в нативном формате AI Proxy
print(response)
# {
#     "items": [
#         {
#             "food_name_ru": "Сэндвич с сыром",
#             "food_name_en": "Cheese Sandwich",
#             "portion_weight_g": 450.0,  # 3x150g
#             "calories": 750,
#             "protein_g": 30.0,
#             "fat_g": 25.0,
#             "carbs_g": 90.0
#         }
#     ],
#     "total": {
#         "calories": 750,
#         "protein_g": 30.0,
#         "fat_g": 25.0,
#         "carbs_g": 90.0
#     },
#     "model_notes": "High carb meal"
# }
```

## Формат данных

### Входные данные (запрос)

```python
{
    "image_url": str,        # URL изображения или data URL
    "user_comment": str,     # Опционально: комментарий пользователя
    "locale": str           # Язык: "ru" или "en"
}
```

### Выходные данные (AI Proxy формат)

```python
{
    "items": [
        {
            "food_name_ru": str,
            "food_name_en": str,
            "portion_weight_g": float,
            "calories": int,
            "protein_g": float,
            "fat_g": float,
            "carbs_g": float
        }
    ],
    "total": {
        "calories": int,
        "protein_g": float,
        "fat_g": float,
        "carbs_g": float
    },
    "model_notes": str  # Опционально
}
```

### Legacy формат (после адаптера)

```python
{
    "recognized_items": [
        {
            "name": str,
            "confidence": float,
            "estimated_weight": int,
            "calories": int,
            "protein": float,
            "fat": float,
            "carbohydrates": float
        }
    ]
}
```

## Исключения

- `AIProxyError` — базовое исключение
- `AIProxyAuthenticationError` — ошибка авторизации (401)
- `AIProxyValidationError` — ошибка валидации запроса (422)
- `AIProxyServerError` — ошибка сервера (500) или сетевая ошибка
- `AIProxyTimeoutError` — таймаут запроса (>30s)

## Логирование

Модуль использует стандартный Python logger:

```python
import logging

logger = logging.getLogger(__name__)
```

Уровни логирования:
- `INFO` — успешные запросы, базовая информация
- `WARNING` — повторные попытки, нестандартное поведение
- `ERROR` — ошибки API, таймауты, сетевые проблемы
- `DEBUG` — детальная информация о запросах/ответах

## Миграция со старого кода

### Было (OpenRouter напрямую):

```python
from apps.ai.services import AIRecognitionService

service = AIRecognitionService()
result = service.recognize_food(
    image_data_url="data:image/jpeg;base64,...",
    user_description="Описание"
)
```

### Стало (через AI Proxy):

```python
from apps.ai_proxy.service import AIProxyRecognitionService

service = AIProxyRecognitionService()
result = service.recognize_food(
    image_data_url="data:image/jpeg;base64,...",
    user_comment="Описание"  # Теперь называется comment
)
```

Формат ответа остался тот же (legacy формат).

## Тестирование

```bash
# Установка зависимостей
pip install -r requirements.txt

# Проверка подключения
python manage.py shell

>>> from apps.ai_proxy.client import AIProxyClient
>>> client = AIProxyClient()
>>> # Если ошибок нет, то настройки корректны
```

## Безопасность

- AI Proxy доступен только через Tailscale VPN
- API ключ передается через заголовок `X-API-Key`
- Таймаут 30 секунд для защиты от зависших запросов
- Валидация всех входных данных на стороне AI Proxy

## Troubleshooting

### Ошибка: "AI_PROXY_URL is not set"

Проверьте `.env`:
```bash
AI_PROXY_URL=http://100.84.210.65:8001
```

### Ошибка: "Authentication failed (401)"

Проверьте `AI_PROXY_SECRET` в `.env`.

### Ошибка: "Connection timeout"

1. Проверьте подключение к Tailscale
2. Убедитесь, что AI Proxy сервис запущен
3. Проверьте файрвол

### Ошибка: "Server error (500)"

Проверьте логи AI Proxy сервиса для деталей.

## См. также

- [API Documentation](../../../docs/API_DOCS.md) — полная документация AI Proxy API
- [Django REST Framework](https://www.django-rest-framework.org/)
- [httpx Documentation](https://www.python-httpx.org/)
