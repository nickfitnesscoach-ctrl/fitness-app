# Тестирование функциональности "Добавить в дневник"

## Что было сделано

### 1. Изучен бэкенд API
- **Модели**: `Meal`, `FoodItem` в `backend/apps/nutrition/models.py`
- **Эндпоинты**:
  - `POST /api/v1/meals/` - создание приёма пищи
  - `POST /api/v1/meals/{meal_id}/items/` - добавление блюда к приёму

### 2. Добавлены TypeScript типы
В `frontend/src/services/api.ts`:
- `Meal` - интерфейс приёма пищи
- `FoodItem` - интерфейс блюда
- `CreateMealRequest` - payload для создания meal
- `CreateFoodItemRequest` - payload для добавления food item

### 3. Улучшены API функции
- `api.createMeal()` - теперь с типами и улучшенным логированием
- `api.addFoodItem()` - изменен с `fetchWithTimeout` на `fetchWithRetry` для надежности
- Добавлена детальная обработка ошибок

### 4. Обновлен FoodLogPage.tsx
- Исправлен тип возвращаемого значения `getMealTypeByTime()`
- Улучшено логирование в `handleSaveMeal()`
- Добавлено отображение ошибок сохранения в UI
- Добавлены Telegram alerts для ошибок

## Контракт API (бэкенд → фронт)

### Создание приёма пищи
```typescript
// Request
POST /api/v1/meals/
{
  "date": "2025-11-30",
  "meal_type": "BREAKFAST" | "LUNCH" | "DINNER" | "SNACK"
}

// Response (201 Created)
{
  "id": 123,
  "meal_type": "BREAKFAST",
  "meal_type_display": "Завтрак",
  "date": "2025-11-30",
  "created_at": "2025-11-30T10:30:00Z",
  "items": [],
  "total": {
    "calories": 0,
    "protein": 0,
    "fat": 0,
    "carbohydrates": 0
  }
}
```

### Добавление блюда к приёму
```typescript
// Request
POST /api/v1/meals/123/items/
{
  "name": "Апельсин — 2 дольки",
  "grams": 100,
  "calories": 47,
  "protein": 0.9,
  "fat": 0.1,
  "carbohydrates": 11.8
}

// Response (201 Created)
{
  "id": 456,
  "name": "Апельсин — 2 дольки",
  "grams": 100,
  "calories": 47.00,
  "protein": 0.90,
  "fat": 0.10,
  "carbohydrates": 11.80,
  "created_at": "2025-11-30T10:30:05Z",
  "updated_at": "2025-11-30T10:30:05Z"
}
```

## Тестирование (Manual QA)

### Шаг 1: Открыть Mini App
1. Открыть Telegram бота
2. Нажать кнопку "Открыть приложение"
3. Перейти на страницу "Дневник питания"

### Шаг 2: Распознать еду
1. Сфотографировать/загрузить фото еды
2. Дождаться распознавания (должны появиться блюда)
3. Выбрать блюда для сохранения (галочка)

### Шаг 3: Сохранить в дневник
1. Нажать кнопку "Добавить в дневник"
2. **Ожидаемое поведение**:
   - Кнопка показывает "Сохраняем..." с spinner
   - В DevTools → Network вкладка:
     - `POST /api/v1/meals/` → 201 Created
     - Несколько `POST /api/v1/meals/{id}/items/` → 201 Created
   - Telegram alert "Приём пищи сохранён!"
   - Переход на страницу `/client`

### Шаг 4: Проверить в DevTools Console
Логи должны показывать:
```
[API] Creating meal: BREAKFAST for 2025-11-30
[API] Meal created successfully: id=123
[FoodLog] Meal created: {id: 123, ...}
[API] Adding food item "Апельсин — 2 дольки" to meal 123
[API] Food item added successfully: id=456
[FoodLog] All food items added successfully: [...]
```

### Возможные ошибки и решения

#### Ошибка 401 Unauthorized
**Причина**: Telegram headers не передаются или неверные
**Решение**: Перезапустить Mini App из Telegram

#### Ошибка 400 Bad Request
**Причина**: Невалидные данные в payload
**Проверить**:
- `date` в формате `YYYY-MM-DD`
- `meal_type` в списке: BREAKFAST, LUNCH, DINNER, SNACK
- Все поля КБЖУ - числа

#### Ошибка 404 Not Found (при добавлении items)
**Причина**: Meal не создался или не найден
**Проверить**: Логи создания meal в консоли

## Дальнейшие улучшения (опционально)

1. **Страница дневника** (`/client`):
   - Отображение сохраненных приёмов пищи
   - Просмотр дневной статистики КБЖУ

2. **Редактирование**:
   - Редактирование сохраненных блюд
   - Удаление приёмов пищи

3. **Offline-режим**:
   - Сохранение в localStorage при отсутствии сети
   - Синхронизация при восстановлении связи
