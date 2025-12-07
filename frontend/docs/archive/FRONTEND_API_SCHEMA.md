# FoodMind AI - Frontend API Schema

## Обзор
Документация JSON API для фронтенд-разработки Telegram Mini App.

---

## 1. Аутентификация пользователя

### POST `/api/v1/telegram/auth/`

Аутентификация через Telegram Mini App WebApp.

**Headers:**
```json
{
  "X-Telegram-Init-Data": "<initData from Telegram.WebApp.initData>"
}
```

**Response:**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "id": 1,
    "username": "tg_123456789",
    "telegram_id": 123456789,
    "first_name": "Николай",
    "last_name": "Иванов",
    "completed_ai_test": true
  }
}
```

**Использование токена:**
```javascript
// Все последующие запросы должны включать заголовок:
Authorization: Bearer <access_token>
```

---

## 2. Профиль пользователя

### GET `/api/v1/telegram/profile/`

Получить полный профиль текущего пользователя.

**Headers:**
```json
{
  "Authorization": "Bearer <jwt_token>"
}
```

**Response:**
```json
{
  "telegram_id": 123456789,
  "username": "nickfitness",
  "first_name": "Николай",
  "last_name": "Иванов",
  "language_code": "ru",
  "is_premium": false,
  "ai_test_completed": true,
  "assigned_calories": 2100,
  "assigned_protein": 130.00,
  "assigned_fat": 70.00,
  "assigned_carbs": 240.00
}
```

**Примечание:** КБЖУ назначается тренером в панели управления после прохождения теста.

---

## 3. Данные AI теста (полная структура)

### GET `/api/v1/users/profile/` (расширенный профиль)

**Response:**
```json
{
  "id": 1,
  "user": {
    "id": 5,
    "username": "tg_1538788067",
    "first_name": "Николай",
    "last_name": "Фитнес",
    "email": "tg1538788067@telegram.user"
  },

  // Telegram данные
  "telegram_id": 1538788067,
  "telegram_username": "nickfitness",

  // Базовые параметры
  "gender": "M",
  "birth_date": "1995-01-01",
  "weight": 75.0,
  "height": 180,
  "target_weight": 70.0,

  // Активность и цели
  "activity_level": "moderately_active",
  "goal_type": "weight_loss",
  "training_level": "beginner",

  // Массивы целей и ограничений
  "goals": ["back_posture", "strength"],
  "health_restrictions": ["diabetes", "hypertension"],

  // Типы фигуры (1-5 для женщин, 1-4 для мужчин)
  "current_body_type": 2,
  "ideal_body_type": 1,

  // Часовой пояс
  "timezone": "Europe/Moscow",

  // КБЖУ (назначается тренером)
  "assigned_calories": 2100,
  "assigned_protein": 130,
  "assigned_fat": 70,
  "assigned_carbs": 240,

  // План питания и тренировок (назначается тренером)
  "trainer_plan": "# Ваш персональный план\n\n...",

  // Метаданные
  "created_at": "2025-11-20T18:21:33.123456Z",
  "updated_at": "2025-11-20T18:21:33.123456Z"
}
```

---

## 4. Справочники (Enums)

### 4.1 Gender (Пол)
```json
{
  "male": "M",
  "female": "F"
}
```

### 4.2 Activity Level (Уровень активности)
```json
{
  "sedentary": "Минимальная - сидячий образ жизни, <3000 шагов",
  "lightly_active": "Низкая - бытовые дела, 3000-7000 шагов",
  "moderately_active": "Средняя - активная работа, 7000-12000 шагов",
  "very_active": "Высокая - постоянное движение, >12000 шагов"
}
```

### 4.3 Goal Type (Цель)
```json
{
  "weight_loss": "Снижение веса",
  "maintenance": "Поддержание веса",
  "weight_gain": "Набор массы"
}
```

### 4.4 Training Level (Уровень тренированности)
```json
{
  "beginner": "Новичок",
  "intermediate": "Средний",
  "advanced": "Продвинутый"
}
```

### 4.5 Body Goals (Цели по телу)
```json
[
  "back_posture",      // Спина и осанка
  "strength",          // Общая сила
  "endurance",         // Выносливость
  "flexibility",       // Гибкость
  "muscle_tone",       // Мышечный тонус
  "abs",              // Пресс
  "legs",             // Ноги
  "arms",             // Руки
  "chest"             // Грудь
]
```

### 4.6 Health Restrictions (Ограничения по здоровью)
```json
[
  "none",              // Нет ограничений
  "diabetes",          // Диабет
  "hypertension",      // Гипертония
  "joint_issues",      // Проблемы с суставами
  "heart_disease",     // Сердечно-сосудистые
  "back_pain",         // Боли в спине
  "pregnancy",         // Беременность
  "injury"            // Травма
]
```

### 4.7 Body Types (Типы фигуры)

**Женщины - Текущая фигура (1-5):**
```json
{
  "1": "Полная фигура",
  "2": "Склонность к животу и бёдрам",
  "3": "Небольшой избыток веса",
  "4": "Стройная фигура",
  "5": "Очень худая фигура"
}
```

**Женщины - Идеальная фигура (1-3):**
```json
{
  "1": "Стройная подтянутая",
  "2": "Подтянутая с лёгким рельефом",
  "3": "Атлетическая с выраженными мышцами"
}
```

**Мужчины - Текущая фигура (1-4):**
```json
{
  "1": "Крупный, значительный избыток веса",
  "2": "Средний, умеренный избыток",
  "3": "Стройный, небольшой живот",
  "4": "Очень худой, минимум жира"
}
```

**Мужчины - Идеальная фигура (1-3):**
```json
{
  "1": "Поджарый с видимым прессом",
  "2": "Атлетический, развитая мускулатура",
  "3": "Массивный, максимум мышц"
}
```

---

## 5. Примеры использования

### 5.1 Инициализация Telegram Mini App

```javascript
// Получаем initData из Telegram WebApp
const initData = window.Telegram.WebApp.initData;

// Аутентификация
const authResponse = await fetch('/api/v1/telegram/auth/', {
  method: 'POST',
  headers: {
    'X-Telegram-Init-Data': initData
  }
});

const { access, refresh, user } = await authResponse.json();

// Сохраняем токен
localStorage.setItem('access_token', access);
localStorage.setItem('refresh_token', refresh);
```

### 5.2 Получение профиля пользователя

```javascript
const token = localStorage.getItem('access_token');

const profileResponse = await fetch('/api/v1/telegram/profile/', {
  headers: {
    'Authorization': `Bearer ${token}`
  }
});

const profile = await profileResponse.json();

// Проверяем, прошел ли пользователь AI тест
if (!profile.ai_test_completed) {
  // Предлагаем пройти тест в боте
  showTestPrompt();
} else if (!profile.assigned_calories) {
  // Тест пройден, но тренер еще не назначил КБЖУ
  showPendingMessage("Тренер скоро назначит вам план питания");
} else {
  // Всё готово - показываем дашборд
  showDashboard(profile);
}
```

### 5.3 Отображение КБЖУ от тренера

```javascript
// Получаем КБЖУ, назначенное тренером
const {
  assigned_calories,
  assigned_protein,
  assigned_fat,
  assigned_carbs
} = profile;

// Проверяем, что КБЖУ назначено
if (assigned_calories) {
  // Отображаем круговую диаграмму
  const macros = {
    protein: assigned_protein,
    fat: assigned_fat,
    carbs: assigned_carbs,
    calories: assigned_calories
  };

  renderMacroChart(macros);
} else {
  // КБЖУ еще не назначено
  showPendingMessage("Ожидание назначения КБЖУ от тренера");
}
```

### 5.4 Отображение плана от тренера

```javascript
const { trainer_plan } = profile;

if (trainer_plan) {
  // Отображаем план от тренера (Markdown)
  document.getElementById('plan').innerHTML = marked(trainer_plan);
} else {
  // План еще не назначен
  showPendingMessage("Тренер скоро создаст ваш персональный план");
}
```

---

## 6. Типы данных для TypeScript

```typescript
// User types
interface TelegramUser {
  id: number;
  username: string;
  telegram_id: number;
  first_name: string;
  last_name?: string;
  completed_ai_test: boolean;
}

interface AuthResponse {
  access: string;
  refresh: string;
  user: TelegramUser;
}

// Profile types
type Gender = 'M' | 'F';
type ActivityLevel = 'sedentary' | 'lightly_active' | 'moderately_active' | 'very_active';
type GoalType = 'weight_loss' | 'maintenance' | 'weight_gain';
type TrainingLevel = 'beginner' | 'intermediate' | 'advanced';

type BodyGoal =
  | 'back_posture'
  | 'strength'
  | 'endurance'
  | 'flexibility'
  | 'muscle_tone'
  | 'abs'
  | 'legs'
  | 'arms'
  | 'chest';

type HealthRestriction =
  | 'none'
  | 'diabetes'
  | 'hypertension'
  | 'joint_issues'
  | 'heart_disease'
  | 'back_pain'
  | 'pregnancy'
  | 'injury';

interface UserProfile {
  id: number;
  user: {
    id: number;
    username: string;
    first_name: string;
    last_name: string;
    email: string;
  };

  // Telegram
  telegram_id: number;
  telegram_username?: string;

  // Basic info
  gender: Gender;
  birth_date: string;
  weight: number;
  height: number;
  target_weight?: number;

  // Activity & Goals
  activity_level: ActivityLevel;
  goal_type: GoalType;
  training_level?: TrainingLevel;

  // Arrays
  goals: BodyGoal[];
  health_restrictions: HealthRestriction[];

  // Body types
  current_body_type?: number;
  ideal_body_type?: number;

  // Timezone
  timezone: string;

  // КБЖУ (назначается тренером)
  assigned_calories?: number;
  assigned_protein?: number;
  assigned_fat?: number;
  assigned_carbs?: number;

  // План от тренера
  trainer_plan?: string;

  // Timestamps
  created_at: string;
  updated_at: string;
}

interface TelegramProfile {
  telegram_id: number;
  username?: string;
  first_name: string;
  last_name?: string;
  language_code: string;
  is_premium: boolean;
  ai_test_completed: boolean;
  assigned_calories?: number;
  assigned_protein?: number;
  assigned_fat?: number;
  assigned_carbs?: number;
}
```

---

## 7. Состояния UI

### 7.1 Пользователь не прошел тест

```json
{
  "ai_test_completed": false,
  "assigned_calories": null,
  "assigned_protein": null,
  "assigned_fat": null,
  "assigned_carbs": null
}
```

**UI Action:** Показать кнопку "Пройти AI тест" → Открыть бота

### 7.2 Пользователь прошел тест, но тренер еще не назначил КБЖУ

```json
{
  "ai_test_completed": true,
  "assigned_calories": null,
  "assigned_protein": null,
  "assigned_fat": null,
  "assigned_carbs": null
}
```

**UI Action:** Показать сообщение "Тренер скоро назначит вам план питания"

### 7.3 Пользователь прошел тест и тренер назначил КБЖУ

```json
{
  "ai_test_completed": true,
  "assigned_calories": 2100,
  "assigned_protein": 130,
  "assigned_fat": 70,
  "assigned_carbs": 240,
  "trainer_plan": "# Ваш план..."
}
```

**UI Action:** Показать дашборд с:
- Круговой диаграммой КБЖУ
- Трекером приемов пищи
- Планом от тренера
- Прогрессом по целям

---

## 8. Обработка ошибок

### 8.1 Unauthorized (401)

```json
{
  "error": "Authentication failed"
}
```

**Action:** Повторить аутентификацию через Telegram WebApp

### 8.2 Not Found (404)

```json
{
  "error": "Telegram profile not found"
}
```

**Action:** Перенаправить в бота для прохождения теста

### 8.3 Server Error (500)

```json
{
  "error": "Internal server error"
}
```

**Action:** Показать сообщение об ошибке, попробовать позже

---

## 9. Примечания для разработки

1. **Все даты в формате ISO 8601**: `"2025-11-20T18:21:33.123456Z"`
2. **Числовые значения КБЖУ**: `float` с точностью до 2 знаков
3. **Массивы могут быть пустыми**: `[]`
4. **Optional поля могут быть**: `null` или отсутствовать
5. **Токены JWT**: Обновлять при истечении через `/api/v1/token/refresh/`

---

## 10. API Endpoints (полный список)

```
POST   /api/v1/telegram/auth/           # Аутентификация
GET    /api/v1/telegram/profile/        # Telegram профиль
POST   /api/v1/telegram/save-test/      # Сохранить результаты теста (используется ботом)

GET    /api/v1/users/profile/           # Расширенный профиль
PATCH  /api/v1/users/profile/           # Обновить профиль

POST   /api/v1/token/refresh/           # Обновить токен
```

---

**Версия документации:** 3.1.1
**Дата обновления:** 2025-11-20
**Проект:** FoodMind AI - Telegram Mini App
