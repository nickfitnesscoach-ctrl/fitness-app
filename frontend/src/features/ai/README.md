# AI Feature Module / Модуль AI-функций

Распознавание еды по фото для EatFit24.

## API-контракт

Модуль реализует фронтенд для:
- `POST /api/v1/ai/recognize/` — Старт распознавания (возвращает 202 Accepted)
- `GET /api/v1/ai/task/<id>/` — Поллинг статуса задачи

См. [API_CONTRACT_AI_AND_TELEGRAM.md](/docs/API_CONTRACT_AI_AND_TELEGRAM.md) для полной спецификации.

## Маппинг типов

API использует другие названия полей, чем UI (для обратной совместимости):

| API поле | UI поле | Примечание |
|----------|---------|------------|
| `items` | `recognized_items` | Массив распознанных блюд |
| `amount_grams` | `grams` | Маппинг на уровне API |
| `user_comment` | `comment` | В FileWithComment |

## Meal type mapping (UI → API)

Фронтенд использует типы приёмов пищи в нижнем регистре (русский/английский), а бэкенд требует **UPPERCASE** формат.

**Таблица соответствий:**

| UI (пользователь вводит) | API (отправляется на бэк) | Django Model Choice |
|--------------------------|---------------------------|---------------------|
| `завтрак` / `breakfast` | `BREAKFAST` | `BREAKFAST` - Завтрак |
| `обед` / `lunch` | `LUNCH` | `LUNCH` - Обед |
| `ужин` / `dinner` | `DINNER` | `DINNER` - Ужин |
| `перекус` / `snack` | `SNACK` | `SNACK` - Перекус |
| Любое другое значение | `SNACK` _(fallback)_ | По умолчанию |

**Реализация:**

Маппинг выполняется в `api/ai.api.ts` функцией `mapMealTypeToApi()`:

```typescript
const MEAL_TYPE_MAP: Record<string, string> = {
    'завтрак': 'BREAKFAST',
    'breakfast': 'BREAKFAST',
    'обед': 'LUNCH',
    'lunch': 'LUNCH',
    'ужин': 'DINNER',
    'dinner': 'DINNER',
    'перекус': 'SNACK',
    'snack': 'SNACK',
};
```

Функция автоматически нормализует входное значение (lowercase, trim) и применяет fallback на `SNACK` для неизвестных значений.

**Важно:** Backend модель требует строго одно из значений: `BREAKFAST`, `LUNCH`, `DINNER`, `SNACK` (см. `apps/nutrition/models.py::Meal.MEAL_TYPE_CHOICES`).

## Структура

```
features/ai/
├── api/                    # API-слой (согласованный с контрактом)
│   ├── ai.api.ts           # recognizeFood, getTaskStatus
│   ├── ai.types.ts         # Типы (API + UI маппинг)
│   └── index.ts
├── hooks/                  # React-хуки
│   ├── useFoodBatchAnalysis.ts
│   ├── useTaskPolling.ts
│   └── index.ts
├── lib/                    # Утилиты
│   ├── image.ts            # HEIC-конвертация, валидация
│   └── index.ts
├── model/                  # Типы и константы
│   ├── constants.ts        # POLLING_CONFIG, MEAL_TYPES, ошибки
│   ├── types.ts            # FileWithComment, BatchProgress
│   └── index.ts
├── ui/                     # UI-компоненты
│   ├── Upload/             # Выбор файлов, drag&drop
│   │   ├── SelectedPhotosList.tsx
│   │   ├── UploadDropzone.tsx
│   │   └── index.ts
│   ├── Result/             # Отображение результатов
│   │   ├── BatchResultsModal.tsx
│   │   └── index.ts
│   ├── States/             # Загрузка, ошибки, лимиты
│   │   ├── BatchProcessingScreen.tsx
│   │   ├── LimitReachedModal.tsx
│   │   └── index.ts
│   └── index.ts
├── README.md
└── index.ts                # Публичные экспорты
```

## Использование

```typescript
import { 
  useFoodBatchAnalysis, 
  BatchResultsModal,
  MEAL_TYPE_OPTIONS,
} from '@/features/ai';

// В компоненте
const { startBatch, results, isProcessing } = useFoodBatchAnalysis({
  getDateString: () => '2025-12-22',
  getMealType: () => 'breakfast', // нижний регистр!
  onDailyLimitReached: () => showLimitModal(),
});
```

## Стратегия поллинга

Согласно API-контракту:
- **Интервал**: 1.5 секунды с экспоненциальным backoff
- **Максимальный интервал**: 5 секунд
- **Таймаут клиента**: 60 секунд
- **Таймаут сервера**: 90 секунд (Celery)

## Добавление новых компонентов

- **Новый UI загрузки**: Добавить в `ui/Upload/`
- **Новое отображение результата**: Добавить в `ui/Result/`
- **Новое состояние/модалка**: Добавить в `ui/States/`
- **Новый API-эндпоинт**: Добавить в `api/ai.api.ts`

## Адаптивная верстка камера/загрузка

Страница камеры в `pages/FoodLogPage.tsx`. Для стилей:
- **Safe area insets**: Использовать `pb-[calc(6rem+env(safe-area-inset-bottom))]`
- **Высота на мобильных**: Использовать класс `min-h-dvh`
- **Зона загрузки**: `ui/Upload/UploadDropzone.tsx`
