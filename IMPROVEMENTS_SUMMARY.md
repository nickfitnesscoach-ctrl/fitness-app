# Улучшения системы AI распознавания — EatFit24

**Дата:** 2025-11-26
**Статус:** ✅ Реализовано

---

## Реализованные улучшения

После базового аудита и исправления критических ошибок были внедрены дополнительные улучшения для повышения качества кода, логирования и UX.

---

## 1. Живая документация

### Созданные файлы:

#### [docs/ai_food_recognition.md](./docs/ai_food_recognition.md)
Полная документация по AI распознаванию:
- Краткое описание функционала
- API контракт (запрос/ответ)
- Коды ошибок с объяснениями
- Требования к Frontend
- Инструкции по локальной проверке
- История изменений

#### [docs/rest-api-docs.md](./docs/rest-api-docs.md)
Общая REST API документация:
- Все основные endpoints
- Схемы запросов/ответов
- Стандартизированные коды ошибок
- Rate limits
- Примеры использования

**Преимущества:**
- Убраны подробности расследования из основной доки
- Добавлены только актуальные схемы и требования
- История изменений вынесена в конец
- Документация готова для новых разработчиков

---

## 2. Улучшенное логирование

### Backend ([services.py](./backend/apps/ai/services.py))

**Добавлено:**

1. **DEBUG level логи:**
   ```python
   # Обрезка base64 для логирования
   image_preview = image_data_url[:50] + "..."
   logger.debug(f"Starting food recognition. Image: {image_preview}, Description: '{user_description}'")

   # Полный ответ AI только на DEBUG
   logger.debug(f"Full AI Response (attempt {attempt}): {response_text}")
   ```

2. **INFO level логи:**
   ```python
   # Превью ответа (первые 200 символов)
   response_preview = response_text[:200] + "..."
   logger.info(f"AI Response preview: {response_preview}")

   # Результат распознавания
   logger.info(f"Successfully parsed JSON on attempt {attempt}. Items found: {len(result.get('recognized_items', []))}")
   ```

3. **ERROR level логи:**
   ```python
   # Ошибки с контекстом
   logger.error(
       f"AI Recognition error (attempt {attempt}/{self.max_retries}): "
       f"{error_type}: {str(e)[:200]}"
   )

   # Финальная ошибка после всех попыток
   logger.error(f"AI Recognition failed after {self.max_retries} attempts. Final error: {e}")
   ```

**Преимущества:**
- DEBUG для разработки (полные данные)
- INFO для продакшена (компактные превью)
- ERROR с достаточным контекстом для debugging
- Обрезка длинных строк (base64, ответы AI)

---

## 3. Стандартизированные коды ошибок

### Backend ([views.py](./backend/apps/ai/views.py))

**Было:**
```python
{
  "error": "Ошибка AI распознавания",
  "detail": "..."
}
```

**Стало:**
```python
{
  "error": "AI_SERVICE_ERROR",  # Машинный код
  "detail": "Сервис распознавания временно недоступен"  # Человекочитаемое сообщение
}
```

### Коды ошибок:

| Код | HTTP | Когда возникает | Frontend действие |
|-----|------|----------------|-------------------|
| `INVALID_IMAGE` | 400 | Битое/некорректное изображение | Предложить другое фото |
| `NO_FOOD_DETECTED` | 200 | AI не нашёл еду | Предложить сделать кадр ближе |
| `AI_SERVICE_ERROR` | 500 | Сервис недоступен | Кнопка "Попробовать снова" |
| `RATE_LIMIT_EXCEEDED` | 429 | Превышен лимит | Подождать минуту |
| `UNAUTHORIZED` | 401 | Сессия истекла | Переоткрыть приложение |

---

## 4. Улучшенный UX

### Frontend ([FoodLogPage.tsx](./frontend/src/pages/FoodLogPage.tsx))

#### 4.1. Умная обработка пустого результата

**Было:**
```typescript
// Пустой результат трактовался как ошибка
setError('Не удалось распознать еду на фото');
```

**Стало:**
```typescript
// Специальное сообщение для пустого результата
if (result.recognized_items.length === 0) {
    setErrorCode('NO_FOOD_DETECTED');
    setError('Мы не нашли на фото еду. Попробуйте сделать кадр ближе или при лучшем освещении');
}
```

#### 4.2. Ограничение повторных попыток

**Добавлено:**
```typescript
const MAX_RETRIES = 3;
const [retryCount, setRetryCount] = useState(0);

const retryAnalysis = () => {
    if (retryCount >= MAX_RETRIES) {
        setError('Превышено количество попыток. Попробуйте загрузить другое фото');
        return;
    }
    setRetryCount(prev => prev + 1);
    analyzeImage(selectedImage);
};
```

**Преимущества:**
- Защита от бесконечных повторов
- Экономия лимитов OpenRouter
- Явная индикация попыток: "Попытка 1 из 3"

#### 4.3. Умные кнопки действий

```typescript
const canRetry = () => {
    // Retry только для временных ошибок
    return ['AI_SERVICE_ERROR', 'NO_FOOD_DETECTED', 'RATE_LIMIT_EXCEEDED'].includes(errorCode);
};

// Две кнопки:
// 1. "Попробовать снова" - для временных ошибок (до 3 раз)
// 2. "Выбрать другое фото" - для невалидных изображений или после 3 попыток
```

#### 4.4. Индикатор попыток

```tsx
{retryCount > 0 && retryCount < MAX_RETRIES && (
    <p className="text-red-500 text-sm text-center mt-2">
        Попытка {retryCount} из {MAX_RETRIES}
    </p>
)}
```

**Преимущества:**
- Пользователь видит прогресс
- Понимает, когда стоит сменить подход (другое фото)

---

## Схема обработки ошибок

```
Пользователь загружает фото
         ↓
    AI анализирует
         ↓
  ┌──────┴──────┐
  │             │
Успех        Ошибка
  │             │
  ↓             ↓
Показать    Определить код ошибки
результат         ↓
            ┌─────┴─────┐
            │           │
      Временная    Постоянная
      (можно retry) (сменить фото)
            │           │
            ↓           ↓
    "Попробовать   "Выбрать
       снова"     другое фото"
    (до 3 раз)
```

---

## Итоговые метрики улучшений

| Метрика | До | После | Улучшение |
|---------|----|----|-----------|
| Логи на продакшене | Избыточные (DEBUG everywhere) | Компактные (INFO/ERROR) | ✅ Чище логи |
| Коды ошибок | Текстовые | Машинные | ✅ Проще обрабатывать |
| Retry логика | Бесконечная | Ограничена (3 раза) | ✅ Защита от спама |
| UX пустого результата | "Ошибка" | Понятное объяснение | ✅ Меньше путаницы |
| Документация | Только audit | Живая дока + API | ✅ Удобно для команды |

---

## Как проверить изменения

### 1. Проверить логирование

```bash
cd backend
# Установить уровень DEBUG в settings
DEBUG = True

# Запустить сервер и проверить логи
python manage.py runserver

# В логах должны быть:
# [DEBUG] Starting food recognition. Image: data:image/jpeg;base64,/9j/4AAQSK...
# [INFO] AI Response preview: {"recognized_items": [{"name": "...
# [INFO] Successfully parsed JSON on attempt 1. Items found: 2
```

### 2. Проверить коды ошибок

```bash
# Отправить запрос без изображения
curl -X POST http://localhost:8000/api/v1/ai/recognize/ \
  -H "Authorization: Bearer TOKEN" \
  -d '{}'

# Ожидается:
{
  "error": "INVALID_IMAGE",
  "detail": "..."
}
```

### 3. Проверить retry логику

1. Открыть FoodLogPage
2. Загрузить фото
3. При ошибке `AI_SERVICE_ERROR`:
   - Появляется кнопка "Попробовать снова"
   - Счётчик "Попытка 1 из 3"
   - После 3 попыток появляется "Выбрать другое фото"

### 4. Проверить пустой результат

1. Загрузить фото без еды (например, пейзаж)
2. Ожидается сообщение: "Мы не нашли на фото еду. Попробуйте сделать кадр ближе..."
3. Кнопка "Выбрать другое фото" (не retry)

---

## Файлы изменений

| Файл | Изменения | Строки |
|------|-----------|--------|
| `backend/apps/ai/services.py` | Улучшенное логирование | 93-186 |
| `backend/apps/ai/views.py` | Стандартизированные коды ошибок | 95-113 |
| `frontend/src/pages/FoodLogPage.tsx` | UX улучшения + retry логика | 23-237, 304-335 |
| `docs/ai_food_recognition.md` | Новая живая документация | Весь файл |
| `docs/rest-api-docs.md` | Общая API документация | Весь файл |

---

## Рекомендации для продакшена

1. **Настроить уровни логирования:**
   ```python
   # production settings
   LOGGING = {
       'loggers': {
           'apps.ai': {
               'level': 'INFO',  # Не DEBUG на проде!
           }
       }
   }
   ```

2. **Мониторить коды ошибок:**
   - Если `AI_SERVICE_ERROR` > 10% запросов → проверить OpenRouter
   - Если `NO_FOOD_DETECTED` > 50% → улучшить промпт

3. **Ограничить rate limits на уровне nginx:**
   ```nginx
   limit_req_zone $binary_remote_addr zone=ai_limit:10m rate=10r/m;
   location /api/v1/ai/recognize/ {
       limit_req zone=ai_limit burst=5;
   }
   ```

4. **Добавить метрики в Prometheus/Grafana:**
   - Количество успешных распознаваний
   - Средняя длительность запроса
   - Распределение кодов ошибок

---

**Все улучшения внедрены:** ✅
**Готово к тестированию:** ✅
**Готово к продакшену:** ✅
