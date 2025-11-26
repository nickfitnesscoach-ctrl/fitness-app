# AI распознавание еды по фото

**Версия API:** v1
**Endpoint:** `POST /api/v1/ai/recognize/`
**Статус:** ✅ Активно

---

## Краткое описание

Система распознавания позволяет пользователям загружать фото блюд и автоматически получать:
- Список распознанных продуктов/блюд
- Вес каждого блюда в граммах
- Калорийность и КБЖУ (белки, жиры, углеводы)
- Итоговые показатели по всем блюдам

**Технологии:**
- Backend: Django REST Framework
- AI: OpenRouter API (модель GPT-5 Image Mini)
- Аутентификация: Telegram WebApp headers / JWT
- Rate limiting: 10 запросов/мин, 100 запросов/день (по IP)

---

## API контракт

### Запрос

**URL:** `POST /api/v1/ai/recognize/`

**Headers:**
```
Content-Type: application/json
Authorization: Bearer <JWT_TOKEN>
# ИЛИ для Telegram WebApp:
X-Telegram-Init-Data: <init_data>
X-Telegram-User-Id: <user_id>
X-Telegram-User-Hash: <hash>
```

**Body:**
```json
{
  "image": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEA...",
  "description": "Овсянка на молоке 2.5%, 1 ч.л. сахара"
}
```

**Поля:**
- `image` (обязательно) — изображение в формате Base64 data URL (JPEG/PNG)
  - Максимальный размер: 10 MB
  - Максимальное разрешение: 4096x4096 px
- `description` (опционально) — текстовое описание для улучшения точности распознавания
  - Максимум 500 символов
  - Примеры: "3 сэндвича", "каша с мёдом и маслом"

---

### Успешный ответ

**HTTP 200 OK**

```json
{
  "recognized_items": [
    {
      "name": "Куриная грудка",
      "grams": 150,
      "calories": 165,
      "protein": 31.0,
      "fat": 3.6,
      "carbohydrates": 0.0
    },
    {
      "name": "Рис отварной",
      "grams": 200,
      "calories": 260,
      "protein": 5.4,
      "fat": 0.6,
      "carbohydrates": 56.0
    }
  ],
  "total_calories": 425.0,
  "total_protein": 36.4,
  "total_fat": 4.2,
  "total_carbohydrates": 56.0
}
```

**Структура `recognized_items[i]`:**
- `name` — название блюда/продукта (string)
- `grams` — вес в граммах (integer)
- `calories` — калорийность (number)
- `protein` — белки в граммах (number)
- `fat` — жиры в граммах (number)
- `carbohydrates` — углеводы в граммах (number)

**Totals:**
- Все поля `total_*` — суммарные значения по всем распознанным элементам

---

### Пустой результат

Если AI не распознал еду на фото, возвращается пустой список:

**HTTP 200 OK**

```json
{
  "recognized_items": [],
  "total_calories": 0,
  "total_protein": 0,
  "total_fat": 0,
  "total_carbohydrates": 0
}
```

**Frontend обработка:** Показать сообщение "Не удалось распознать еду на фото. Попробуйте другое изображение" с кнопкой выбора другого фото.

---

### Ошибки

#### 400 Bad Request — Некорректные данные

```json
{
  "error": "INVALID_IMAGE",
  "detail": "Некорректный формат изображения. Поддерживаются только JPEG и PNG"
}
```

**Возможные коды ошибок:**
- `INVALID_IMAGE` — неверный формат, битое изображение или слишком большой размер
- `MISSING_IMAGE` — отсутствует поле `image` в запросе

---

#### 401 Unauthorized — Не авторизован

```json
{
  "error": "UNAUTHORIZED",
  "detail": "Требуется аутентификация"
}
```

**Решение:** Пользователь должен открыть приложение через Telegram бота заново.

---

#### 429 Too Many Requests — Превышен лимит

```json
{
  "error": "RATE_LIMIT_EXCEEDED",
  "detail": "Превышен лимит запросов. Попробуйте через минуту"
}
```

**Лимиты:**
- 10 запросов в минуту (по IP)
- 100 запросов в день (по IP)

---

#### 500 Internal Server Error — Ошибка сервера

```json
{
  "error": "AI_SERVICE_ERROR",
  "detail": "Сервис распознавания временно недоступен. Попробуйте позже"
}
```

**Возможные причины:**
- OpenRouter API недоступен
- Ошибка парсинга ответа от AI
- Внутренняя ошибка сервера

**Frontend обработка:** Показать кнопку "Попробовать снова" (максимум 3 попытки).

---

## Требования Frontend

### Отправка запроса

```typescript
// Пример из FoodLogPage.tsx
const analyzeImage = async (imageBase64: string) => {
    setAnalyzing(true);
    setError(null);
    setAnalysisResult(null);

    try {
        const result = await api.recognizeFood(imageBase64);

        if (result.recognized_items && result.recognized_items.length > 0) {
            setAnalysisResult(result);
            setSelectedItems(new Set(result.recognized_items.map((_, i) => i)));
        } else {
            setError('Не удалось распознать еду на фото. Попробуйте другое изображение.');
        }
    } catch (err: any) {
        console.error('Analysis failed:', err);
        setError(err.message || 'Ошибка при анализе фото');
    } finally {
        setAnalyzing(false);
    }
};
```

### Обработка ошибок

```typescript
// Обработка кодов ошибок
const handleError = (error: any) => {
    const errorCode = error.error || 'UNKNOWN_ERROR';

    switch (errorCode) {
        case 'INVALID_IMAGE':
            return 'Некорректное изображение. Попробуйте другое фото';
        case 'AI_SERVICE_ERROR':
            return 'Сервис временно недоступен. Попробуйте снова';
        case 'RATE_LIMIT_EXCEEDED':
            return 'Слишком много запросов. Подождите минуту';
        case 'UNAUTHORIZED':
            return 'Сессия истекла. Откройте приложение заново';
        default:
            return error.detail || 'Произошла ошибка';
    }
};
```

### Retry логика

```typescript
const [retryCount, setRetryCount] = useState(0);
const MAX_RETRIES = 3;

const retryAnalysis = () => {
    if (retryCount >= MAX_RETRIES) {
        setError('Превышено количество попыток. Попробуйте другое фото');
        return;
    }

    setRetryCount(prev => prev + 1);
    if (selectedImage) {
        analyzeImage(selectedImage);
    }
};
```

---

## Как проверить локально

### Backend

1. **Запустить тесты:**
   ```bash
   cd backend
   python manage.py test apps.ai.tests.AIRecognitionAPITestCase
   ```

2. **Проверить endpoint через curl:**
   ```bash
   # С JWT токеном
   curl -X POST http://localhost:8000/api/v1/ai/recognize/ \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     -d '{"image": "data:image/jpeg;base64,...", "description": ""}'
   ```

3. **Проверить логи:**
   ```bash
   # Логи должны содержать:
   [INFO] OpenRouter client initialized successfully
   [INFO] Starting AI recognition for user testuser
   [INFO] AI recognized 2 items
   ```

### Frontend

1. **Запустить dev сервер:**
   ```bash
   cd frontend
   npm run dev
   ```

2. **Проверить функционал:**
   - Открыть страницу "Дневник питания"
   - Загрузить фото еды
   - Дождаться распознавания
   - Проверить корректность отображения результатов
   - При ошибке проверить кнопку "Попробовать снова"

3. **Проверить в консоли браузера:**
   ```javascript
   // Успешный запрос
   [API] Calling AI recognize endpoint
   [API] AI recognized 2 items

   // Ошибка
   [API] AI recognition error: AI_SERVICE_ERROR
   ```

---

## Конфигурация

### Переменные окружения (.env)

```bash
# OpenRouter API
OPENROUTER_API_KEY=sk-or-v1-your-api-key-here
OPENROUTER_SITE_URL=http://localhost:8000
OPENROUTER_SITE_NAME=FoodMind AI

# Limits (опционально)
AI_MAX_RETRIES=3
```

### Получение API ключа

1. Зарегистрироваться на https://openrouter.ai/
2. Получить ключ на https://openrouter.ai/keys
3. Добавить в `.env` файл

**Формат ключа:** `sk-or-v1-xxxxxxxxxxxxx` (минимум 32 символа)

---

## Известные ограничения

1. **Rate limits:**
   - 10 запросов/минуту с одного IP
   - 100 запросов/день с одного IP

2. **Размер изображения:**
   - Максимум 10 MB
   - Максимальное разрешение 4096x4096 px

3. **Поддерживаемые форматы:**
   - JPEG
   - PNG

4. **Точность распознавания:**
   - Зависит от качества фото
   - Лучшие результаты при съёмке сверху при хорошем освещении

---

## История изменений

### 2025-11-26 — Исправление критических ошибок

**Проблемы:**
1. Несоответствие схемы ответа Backend ↔ Frontend
   - Backend возвращал вложенный объект `{ "data": { "recognized_items": [...] } }`
   - Frontend ожидал `{ "recognized_items": [...] }`
   - Backend использовал `estimated_weight`, Frontend — `grams`

2. Кнопка "Попробовать снова" сбрасывала состояние вместо повторного запроса

**Исправления:**
- Убрана обёртка `data` в serializer
- Добавлено маппирование `estimated_weight` → `grams`
- Реализована корректная retry логика во Frontend
- Добавлены 7 unit тестов для проверки API

**Файлы:**
- `backend/apps/ai/serializers.py` (строки 244-290)
- `frontend/src/pages/FoodLogPage.tsx` (строки 197-201, 266-277)
- `backend/apps/ai/tests.py` (новый файл, 230 строк)

---

## Дополнительные ресурсы

- [OpenRouter API Documentation](https://openrouter.ai/docs)
- [REST API общая документация](./rest-api-docs.md)
- [Аудит системы (подробный)](../auditAi.md)
