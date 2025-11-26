# Аудит и исправление AI распознавания еды в EatFit24

**Дата:** 2025-11-26
**Проект:** EatFit24 (root: `/fitness-app`)
**Компоненты:** Frontend (React/TypeScript) + Backend (Django/DRF)

---

## Краткое резюме

**Проблема:** В мини-апе Telegram на вкладке "Дневник питания" после загрузки фото пользователь видел ошибку "Ошибка AI распознавания", а кнопка "Попробовать снова" не работала.

**Причины:**
1. **Несоответствие схемы ответа Backend ↔ Frontend**
   - Backend возвращал: `{ "data": { "recognized_items": [...] } }`
   - Frontend ожидал: `{ "recognized_items": [...] }`
   - Backend использовал поле `estimated_weight`, а Frontend ожидал `grams`

2. **Кнопка "Попробовать снова" не делала повторную попытку**
   - Вместо повторного запроса к AI просто сбрасывала состояние к начальному экрану
   - Пользователь был вынужден загружать фото заново

**Решение:**
- Исправлена схема ответа в backend serializer
- Добавлен правильный retry механизм во frontend
- Добавлены тесты для проверки корректности работы

---

## 1. Найденные проблемы

### Проблема 1: Несоответствие схемы ответа (КРИТИЧЕСКАЯ)

**Файл:** `backend/apps/ai/serializers.py` (строки 244-272)

**Было:**
```python
class AIRecognitionResponseSerializer(serializers.Serializer):
    """Serializer for AI recognition response."""
    data = serializers.DictField(child=serializers.JSONField())

    def to_representation(self, instance):
        items = instance.get("recognized_items", [])
        # ...
        return {
            "data": {  # ← Лишняя обёртка!
                "recognized_items": items,
                "summary": { ... }
            }
        }
```

**Проблема:**
- Backend оборачивал `recognized_items` в объект `data`
- Backend возвращал `estimated_weight`, но Frontend ожидал `grams`
- Несоответствие приводило к тому, что Frontend пытался прочитать `result.recognized_items`, но получал `undefined`, так как реальные данные были в `result.data.recognized_items`

**Файл:** `frontend/src/pages/FoodLogPage.tsx` (строка 78-86)

```typescript
const result = await api.recognizeFood(imageBase64);

if (result.recognized_items && result.recognized_items.length > 0) {
    // ← Здесь result.recognized_items === undefined!
    setAnalysisResult(result);
    setSelectedItems(new Set(result.recognized_items.map((_: any, i: number) => i)));
} else {
    setError('Не удалось распознать еду на фото. Попробуйте другое изображение.');
}
```

---

### Проблема 2: Кнопка "Попробовать снова" не работает

**Файл:** `frontend/src/pages/FoodLogPage.tsx` (строки 190-195, 266-270)

**Было:**
```typescript
const resetState = () => {
    setSelectedImage(null);  // ← Удаляет изображение!
    setAnalysisResult(null);
    setSelectedItems(new Set());
    setError(null);
};

// В JSX:
<button onClick={resetState} className="...">
    Попробовать снова
</button>
```

**Проблема:**
- При клике на "Попробовать снова" состояние полностью сбрасывалось
- Изображение удалялось (`setSelectedImage(null)`)
- Пользователь возвращался к начальному экрану и должен был загружать фото заново
- Функция НЕ вызывала `analyzeImage()` для повторной попытки

---

## 2. Реализованные исправления

### Исправление 1: Схема ответа Backend

**Файл:** `backend/apps/ai/serializers.py`

```diff
 class AIRecognitionResponseSerializer(serializers.Serializer):
     """Serializer for AI recognition response."""
-    data = serializers.DictField(child=serializers.JSONField())

     def to_representation(self, instance):
-        """Format response according to API docs with totals."""
+        """
+        Format response to match frontend expectations.
+
+        Frontend expects:
+        {
+          "recognized_items": [...],
+          "total_calories": number,
+          "total_protein": number,
+          "total_fat": number,
+          "total_carbohydrates": number
+        }
+
+        Also maps backend field names to frontend:
+        - estimated_weight -> grams
+        """
         items = instance.get("recognized_items", [])

+        # Map field names for frontend compatibility
+        mapped_items = []
+        for item in items:
+            mapped_item = {
+                "name": item.get("name", ""),
+                "grams": item.get("estimated_weight", 0),  # Map estimated_weight -> grams
+                "calories": item.get("calories", 0),
+                "protein": item.get("protein", 0),
+                "fat": item.get("fat", 0),
+                "carbohydrates": item.get("carbohydrates", 0),
+            }
+            mapped_items.append(mapped_item)
+
         # Calculate totals
         total_calories = sum(item.get("calories", 0) for item in items)
         total_protein = sum(item.get("protein", 0) for item in items)
         total_fat = sum(item.get("fat", 0) for item in items)
         total_carbs = sum(item.get("carbohydrates", 0) for item in items)

         return {
-            "data": {
-                "recognized_items": items,
-                "summary": {
-                    "total_items": len(items),
-                    "totals": {
-                        "calories": round(total_calories, 1),
-                        "protein": round(total_protein, 1),
-                        "fat": round(total_fat, 1),
-                        "carbohydrates": round(total_carbs, 1)
-                    },
-                    "formatted": f"Итого: ..."
-                }
-            }
+            "recognized_items": mapped_items,
+            "total_calories": round(total_calories, 1),
+            "total_protein": round(total_protein, 1),
+            "total_fat": round(total_fat, 1),
+            "total_carbohydrates": round(total_carbs, 1)
         }
```

**Что изменено:**
- Убрана лишняя обёртка `data`
- Добавлено маппирование `estimated_weight` → `grams`
- Упрощена структура ответа: теперь Frontend сразу получает `recognized_items` на верхнем уровне
- Добавлены поля `total_*` для совместимости с Frontend

---

### Исправление 2: Кнопка "Попробовать снова"

**Файл:** `frontend/src/pages/FoodLogPage.tsx`

```diff
     const resetState = () => {
         setSelectedImage(null);
         setAnalysisResult(null);
         setSelectedItems(new Set());
         setError(null);
     };

+    const retryAnalysis = () => {
+        if (selectedImage) {
+            analyzeImage(selectedImage);
+        }
+    };
```

```diff
         {/* Error message */}
         {error && (
             <div className="bg-red-50 border border-red-200 rounded-2xl p-4">
                 <p className="text-red-600 text-center">{error}</p>
                 <button
-                    onClick={resetState}
-                    className="w-full mt-3 bg-red-100 text-red-700 py-2 rounded-xl font-medium"
+                    onClick={retryAnalysis}
+                    disabled={analyzing}
+                    className="w-full mt-3 bg-red-500 text-white py-2 rounded-xl font-medium hover:bg-red-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                 >
-                    Попробовать снова
+                    {analyzing ? 'Анализируем...' : 'Попробовать снова'}
                 </button>
             </div>
         )}
```

**Что изменено:**
- Добавлена функция `retryAnalysis()`, которая повторно вызывает `analyzeImage(selectedImage)`
- Кнопка теперь вызывает `retryAnalysis` вместо `resetState`
- Кнопка блокируется во время анализа (`disabled={analyzing}`)
- Улучшен визуальный стиль кнопки (красный фон для привлечения внимания)
- Текст кнопки меняется на "Анализируем..." во время обработки

---

## 3. Добавленные тесты

**Файл:** `backend/apps/ai/tests.py`

Добавлены комплексные тесты для проверки:

1. **`test_successful_recognition`** - Успешное распознавание с проверкой структуры ответа
   - Проверяет наличие полей `recognized_items`, `total_calories`, `total_protein`, `total_fat`, `total_carbohydrates`
   - Проверяет маппирование `estimated_weight` → `grams`
   - Проверяет корректность расчёта totals

2. **`test_empty_recognition`** - Когда AI не распознал еду
   - Проверяет корректную обработку пустого ответа

3. **`test_ai_service_error`** - Обработка ошибок AI сервиса
   - Проверяет HTTP 500 при ошибке AI
   - Проверяет структуру ответа с ошибкой

4. **`test_invalid_image_format`** - Валидация формата изображения
   - Проверяет HTTP 400 при неверном формате

5. **`test_missing_image`** - Отсутствие изображения в запросе
   - Проверяет HTTP 400 при отсутствующем поле `image`

6. **`test_unauthenticated_request`** - Запрос без аутентификации
   - Проверяет HTTP 401 для неаутентифицированных пользователей

7. **`test_with_user_description`** - Распознавание с описанием пользователя
   - Проверяет, что описание учитывается AI

**Пример теста:**
```python
def test_successful_recognition(self):
    """Test successful food recognition with mocked AI response."""
    mock_response = {
        "recognized_items": [
            {
                "name": "Куриная грудка",
                "confidence": 0.95,
                "estimated_weight": 150,
                "calories": 165,
                "protein": 31.0,
                "fat": 3.6,
                "carbohydrates": 0.0
            }
        ]
    }

    with patch.object(AIRecognitionService, 'recognize_food', return_value=mock_response):
        response = self.client.post(self.url, data={...})

    self.assertEqual(response.status_code, status.HTTP_200_OK)
    data = response.json()

    # Check response structure
    self.assertIn('recognized_items', data)
    self.assertIn('grams', data['recognized_items'][0])
    self.assertEqual(data['recognized_items'][0]['grams'], 150)
```

---

## 4. Проверка конфигурации

### AI сервис (OpenRouter)

**Файл:** `backend/config/settings/base.py` (строки 473-477)

```python
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_SITE_URL = os.environ.get("OPENROUTER_SITE_URL", "http://localhost:8000")
OPENROUTER_SITE_NAME = os.environ.get("OPENROUTER_SITE_NAME", "FoodMind AI")
OPENROUTER_MODEL = "openai/gpt-5-image-mini"  # GPT-5 Image Mini
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
```

**Проверено:**
- Настройки корректны
- API ключ читается из `.env` файла
- Валидация API ключа происходит в `AIRecognitionService.__init__()` (строки 21-76)
- Есть проверки на формат ключа (`sk-or-v1-...`), длину и placeholder значения

**Файл:** `backend/apps/ai/services.py` (строки 19-76)

```python
def __init__(self):
    """Initialize OpenRouter client with comprehensive API key validation."""
    api_key = settings.OPENROUTER_API_KEY

    # Validate API key exists
    if not api_key or api_key == "":
        raise ImproperlyConfigured("OPENROUTER_API_KEY is not set in settings...")

    # Validate API key format
    if not api_key.startswith("sk-or-v1-"):
        raise ImproperlyConfigured("Invalid OPENROUTER_API_KEY format...")

    # Check for placeholder/example keys
    placeholder_patterns = ["sk-or-v1-your", "sk-or-v1-example", ...]
    if any(api_key.startswith(pattern) for pattern in placeholder_patterns):
        raise ImproperlyConfigured("OPENROUTER_API_KEY appears to be a placeholder value...")
```

---

## 5. Как проверить исправления

### Локальная проверка Backend

1. **Запустить тесты:**
   ```bash
   cd backend
   python manage.py test apps.ai.tests.AIRecognitionAPITestCase
   ```

2. **Проверить endpoint вручную:**
   ```bash
   # Создать тестовое изображение
   python -c "import base64; print('data:image/jpeg;base64,' + base64.b64encode(open('test.jpg', 'rb').read()).decode())" > test_image.txt

   # Отправить запрос (с валидным JWT токеном)
   curl -X POST http://localhost:8000/api/v1/ai/recognize/ \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     -d '{"image": "data:image/jpeg;base64,...", "description": ""}'
   ```

3. **Проверить структуру ответа:**
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
       }
     ],
     "total_calories": 165,
     "total_protein": 31.0,
     "total_fat": 3.6,
     "total_carbohydrates": 0.0
   }
   ```

### Локальная проверка Frontend

1. **Запустить dev сервер:**
   ```bash
   cd frontend
   npm run dev
   ```

2. **Проверить функционал:**
   - Открыть страницу "Дневник питания"
   - Загрузить любое фото еды
   - Дождаться распознавания
   - При ошибке нажать "Попробовать снова" → должен произойти повторный запрос
   - Проверить, что результаты отображаются корректно

3. **Проверить в консоли браузера:**
   ```javascript
   // Должны быть логи вида:
   [API] Calling AI recognize endpoint
   [API] AI recognized 2 items
   ```

---

## 6. Возможные дополнительные проблемы

### 6.1. Отсутствующий API ключ OpenRouter

**Симптом:** Ошибка при старте backend:
```
django.core.exceptions.ImproperlyConfigured: OPENROUTER_API_KEY is not set in settings.
```

**Решение:**
1. Получить API ключ на https://openrouter.ai/keys
2. Добавить в `backend/.env`:
   ```
   OPENROUTER_API_KEY=sk-or-v1-your-actual-key-here
   ```

### 6.2. Проблемы с CORS

**Симптом:** Frontend получает CORS ошибку в консоли браузера

**Решение:** Проверить `backend/.env`:
```
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
```

### 6.3. Telegram WebApp аутентификация

**Важно:** Endpoint `/api/v1/ai/recognize/` требует аутентификацию через Telegram WebApp headers:
- `X-Telegram-Init-Data`
- `X-Telegram-User-Id`
- `X-Telegram-User-Hash`

При тестировании через curl используйте JWT токен или мокайте Telegram headers.

---

## 7. Итоги

### Найденные причины поломки:

1. **Несоответствие схемы ответа** (Backend возвращал вложенный `data` объект, Frontend ожидал данные на верхнем уровне)
2. **Несоответствие имён полей** (`estimated_weight` vs `grams`)
3. **Некорректная логика кнопки "Попробовать снова"** (сбрасывала состояние вместо повторного запроса)

### Внесённые изменения:

| Файл | Строки | Изменение |
|------|--------|-----------|
| `backend/apps/ai/serializers.py` | 244-290 | Убрана обёртка `data`, добавлено маппирование полей |
| `frontend/src/pages/FoodLogPage.tsx` | 197-201, 272 | Добавлена функция `retryAnalysis()` |
| `backend/apps/ai/tests.py` | 1-230 | Добавлены 7 тестов для проверки API |

### Проверка завершена:

- ✅ Frontend ожидает корректную структуру ответа
- ✅ Backend возвращает корректную структуру ответа
- ✅ Маппинг полей `estimated_weight` → `grams` работает
- ✅ Кнопка "Попробовать снова" делает повторный запрос
- ✅ Добавлены тесты для проверки корректности работы
- ✅ Конфигурация AI сервиса проверена

### Рекомендации:

1. **Запустить тесты после деплоя:**
   ```bash
   python manage.py test apps.ai.tests
   ```

2. **Проверить логи на продакшене** после первого использования функции распознавания

3. **Мониторить rate limits OpenRouter** (10 запросов/мин, 100 запросов/день на IP)

4. **При необходимости добавить frontend тесты** с testing-library для проверки кнопки "Попробовать снова"

---

**Аудит выполнен:** 2025-11-26
**Статус:** ✅ Все проблемы найдены и исправлены
**Готовность к тестированию:** Да
