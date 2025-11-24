# Roadmap: Единый профиль пользователя и онбординг в WebApp

## 1. Overview / Цели

### Что мы строим
Единую систему профилей пользователей в FoodMind / EatFit24, где:

- **Единый источник правды**: Профиль пользователя хранится в Django (модель `Profile` в `backend/apps/users/models.py`), привязан к `telegram_id`
- **WebApp-first подход**: Telegram WebApp может работать автономно, без обязательного прохождения теста в боте
- **Онбординг в миниапе**: Новые пользователи проходят быструю регистрацию (3-5 экранов) прямо в WebApp
- **Тест в боте как расширение**: Опрос в боте не заменяет профиль, а дополняет его и создает сущность "Заявка/Лид" для тренера

### Проблема сейчас
- Пользователь, зашедший в WebApp без прохождения теста, не имеет полноценного профиля
- WebApp не всегда понимает `telegram_id` и получает ошибки (401/403/500)
- Данные дублируются между Django (`Profile`, `TelegramUser`) и SQLAlchemy-таблицами бота (`users`, `survey_answers`)
- Нет четкой логики, кто главный: бот или WebApp

### Целевое состояние
- Любой пользователь Telegram может открыть WebApp и сразу работать (онбординг → цели → дневник)
- Профиль живет в Django, синхронизируется по `telegram_id`
- Бот отправляет результаты теста в Django через API `/api/v1/telegram/save-test/`
- Тренер работает с заявками в панели управления (все данные из Django)

---

## 2. Текущая архитектура данных

### Django models

#### `backend/apps/users/models.py`
**Модель `Profile`** (основной профиль пользователя):
- Связь: `OneToOne` с `auth.User`
- Ключевые поля:
  - `telegram_id` (BigInteger, unique) — связь с Telegram
  - `telegram_username` (String)
  - Базовые данные: `gender`, `birth_date`, `height`, `weight`, `activity_level`, `goal_type`, `target_weight`, `timezone`
  - Уровень тренированности: `training_level`
  - Множественные цели (JSON): `goals` (например, `['weight_loss', 'remove_belly']`)
  - Ограничения по здоровью (JSON): `health_restrictions`
  - Типы фигуры: `current_body_type`, `ideal_body_type`
  - AI рекомендации (JSON): `ai_recommendations`
  - Рекомендованные КБЖУ (диапазоны): `recommended_calories_min/max`, `recommended_protein_min/max` и т.д.

**Автоматическое создание**: При создании `User` автоматически создается пустой `Profile` (сигнал `post_save`).

#### `backend/apps/telegram/models.py`
**Модель `TelegramUser`** (Telegram-специфичные данные):
- Связь: `OneToOne` с `auth.User`
- Ключевые поля:
  - `telegram_id` (BigInteger, unique, indexed) — ID в Telegram
  - `username`, `first_name`, `last_name`, `language_code`, `is_premium`
  - Данные из AI-теста:
    - `ai_test_completed` (Boolean)
    - `ai_test_answers` (JSON) — результаты теста
    - `is_client` (Boolean) — добавлен ли в клиенты тренера
    - `recommended_calories`, `recommended_protein/fat/carbs` — рекомендованные КБЖУ из теста

**Назначение**: Хранит Telegram-специфичную информацию и результаты теста. Дублирует часть КБЖУ из `Profile`, но скоро должен стать вторичным.

#### `backend/apps/nutrition/models.py`
- **`DailyGoal`**: Дневные цели КБЖУ для пользователя
  - `user` (FK to User)
  - `calories`, `protein`, `fat`, `carbohydrates`
  - `source`: `'AUTO'` (рассчитано автоматически) или `'MANUAL'` (установлено вручную)
  - `is_active`: только одна цель активна на пользователя
  - Метод `calculate_goals(user)`: расчет по формуле Миффлина-Сан Жеора

- **`Meal`**: Приемы пищи (завтрак/обед/ужин/перекус)
- **`FoodItem`**: Блюда в рамках приема пищи (FK to Meal)

### Bot SQLAlchemy models

#### `bot/app/models/user.py`
**Модель `User`**:
- `tg_id` (BigInteger, unique) — Telegram ID
- `username`, `full_name`
- `tz`, `utc_offset_minutes` — часовой пояс
- Relationships: `survey_answers`, `plans`

#### `bot/app/models/survey.py`
**Модель `SurveyAnswer`** (результаты опроса в боте):
- `user_id` (FK to `bot.users`)
- Данные опроса: `gender`, `age`, `height_cm`, `weight_kg`, `target_weight_kg`, `activity`, `training_level`
- Цели (JSON): `body_goals`, `health_limitations`
- Типы фигуры: `body_now_id`, `body_now_label`, `body_now_file`, `body_ideal_id`, `body_ideal_label`, `body_ideal_file`
- Часовой пояс: `tz`, `utc_offset_minutes`
- `completed_at`, `created_at`

**Модель `Plan`** (AI-планы):
- `user_id`, `survey_answer_id` (FK)
- `ai_text`, `ai_model`, `prompt_version`

**Назначение**: Изначально были основным хранилищем данных бота. В целевой архитектуре должны стать архивными/дублирующими.

### WebApp authentication

#### `backend/apps/telegram/authentication.py`
Два метода аутентификации:

1. **`TelegramWebAppAuthentication`**:
   - Проверяет подпись `initData` через сервис `webapp_auth`
   - При успешной валидации: создает или обновляет `TelegramUser` и связанный `User`
   - Гарантирует создание `Profile` (через `Profile.objects.get_or_create(user=user)`)

2. **`TelegramHeaderAuthentication`** (через Nginx прокси):
   - Читает заголовки `X-Telegram-ID`, `X-Telegram-First-Name` и т.д.
   - Создает или находит пользователя по `telegram_id`
   - Также гарантирует создание `Profile`

**Проблема**: Автоматически созданный профиль пустой (только defaults). WebApp должен запустить онбординг для заполнения данных.

### Текущие API endpoints

#### Telegram
- `POST /api/v1/telegram/auth/` — аутентификация через initData (возвращает JWT + user data, но WebApp использует Header auth)
- `GET /api/v1/telegram/profile/` — получить TelegramUser профиль (требует аутентификации)
- `POST /api/v1/telegram/save-test/` — сохранить результаты теста из бота
- `GET /api/v1/telegram/applications/` — список заявок (пользователи с `ai_test_completed=True`)
- `GET /api/v1/telegram/clients/` — список клиентов (пользователи с `is_client=True`)

#### Users
- `GET/PATCH /api/v1/users/profile/` — получить/обновить профиль текущего пользователя
- `POST /api/v1/users/auth/register/`, `POST /api/v1/users/auth/login/` — регистрация/логин (не используются в WebApp)

#### Nutrition
- `GET /api/v1/goals/` — получить активную цель КБЖУ
- `PUT/PATCH /api/v1/goals/` — обновить цель вручную
- `POST /api/v1/goals/calculate/` — рассчитать цель по формуле
- `POST /api/v1/goals/set-auto/` — установить автоматическую цель
- `GET /api/v1/meals/?date=YYYY-MM-DD` — дневник питания
- `POST /api/v1/meals/` — создать прием пищи

### Интеграция бот → Django

#### `bot/app/services/django_integration.py`
Функция `send_test_results_to_django()`:
- Отправляет результаты опроса в `POST /api/v1/telegram/save-test/`
- Маппинг полей:
  - `age` → `birth_date` (вычисляется как `current_year - age`)
  - `activity`: `sedentary/light/moderate/active` → `minimal/low/medium/high`
  - `goal`: `fat_loss/muscle_gain/maintenance` → `weight_loss/weight_gain/maintenance`
- Использует retry-логику (3 попытки с exponential backoff)

#### `backend/apps/telegram/views.py::save_test_results`
Endpoint `/api/v1/telegram/save-test/`:
1. Получает `telegram_id` и `answers` из запроса
2. Находит или создает `TelegramUser` (и связанный `User`)
3. Обновляет `Profile` данными из теста
4. Устанавливает `ai_test_completed=True` в `TelegramUser`
5. Создает `DailyGoal` с автоматическим расчетом КБЖУ

**Проблема**: Бот пока еще использует свои SQLAlchemy-таблицы параллельно.

---

## 3. Target Architecture (целевое состояние)

### Единая модель профиля

**Источник правды**: `backend/apps/users/models.py::Profile`

**Ключевой идентификатор**: `telegram_id` (уникальный, indexed)

**Минимальный набор полей для онбординга** (required):
1. `gender` — пол (M/F)
2. `birth_date` или `age` — возраст
3. `height` — рост (см)
4. `weight` — текущий вес (кг)
5. `activity_level` — уровень активности
   - `sedentary` — минимум движения (офис, <5 000 шагов/день)
   - `light` — лёгкая активность (5–7 тыс. шагов, 1 тренировка/нед)
   - `moderate` — средняя (7–10 тыс., 2–3 тренировки/нед)
   - `high` — высокая (тяжёлая работа или 4–5 тренировок/нед)
   - `athlete` — очень высокая (спорт 6–7 раз/нед)
6. `goal_type` — цель (weight_loss/maintenance/weight_gain)

**Дополнительные поля** (optional, заполняются через тест или позже):
- `target_weight` — целевой вес
- `timezone` — часовой пояс
- `training_level` — уровень тренированности
- `goals` (JSON) — множественные цели
- `health_restrictions` (JSON) — ограничения
- `current_body_type`, `ideal_body_type` — типы фигуры
- `ai_recommendations` (JSON) — AI-рекомендации

### API endpoints (целевые)

#### 1. `/api/v1/webapp/auth/` (unified auth для WebApp)
**Метод**: `POST`
**Headers**: `X-Telegram-Init-Data: <initData>`
**Response**:
```json
{
  "user": {
    "id": 123,
    "telegram_id": 987654321,
    "username": "user123",
    "first_name": "John",
    "last_name": "Doe"
  },
  "profile": {
    "is_complete": false,  // профиль заполнен минимально?
    "gender": null,
    "age": null,
    "height": null,
    "weight": null,
    "goal_type": null,
    "activity_level": "sedentary",
    "timezone": null
  },
  "goals": null,  // или { "calories": 2000, ... } если есть
  "is_admin": false
}
```

**Логика**:
- Валидирует `initData`
- Создает или находит пользователя по `telegram_id`
- Возвращает профиль + цели + флаг `is_admin`
- Если профиль неполный (`is_complete=false`), WebApp запускает онбординг

#### 2. `/api/v1/profile/` (получить/обновить профиль)
**GET**: Вернуть текущий профиль пользователя
**PATCH**: Обновить поля профиля

**Request (PATCH)**:
```json
{
  "gender": "M",
  "birth_date": "1990-01-01",
  "height": 180,
  "weight": 80,
  "goal_type": "weight_loss",
  "activity_level": "moderately_active",
  "timezone": "Europe/Moscow"
}
```

**Response**:
```json
{
  "id": 123,
  "telegram_id": 987654321,
  "gender": "M",
  "age": 34,
  "height": 180,
  "weight": 80,
  "goal_type": "weight_loss",
  "activity_level": "moderately_active",
  "is_complete": true
}
```

#### 3. `/api/v1/survey/apply/` (применить результаты теста из бота)
**Метод**: `POST`
**Body**:
```json
{
  "telegram_id": 987654321,
  "first_name": "John",
  "last_name": "Doe",
  "username": "john_doe",
  "answers": {
    "gender": "male",
    "age": 30,
    "height": 180,
    "weight": 80,
    "goal": "fat_loss",
    "activity_level": "medium",
    "training_level": "intermediate",
    "goals": ["weight_loss", "muscle_tone"],
    "health_restrictions": ["none"],
    "current_body_type": 2,
    "ideal_body_type": 3,
    "timezone": "Europe/Moscow"
  }
}
```

**Response**:
```json
{
  "status": "success",
  "user_id": 123,
  "profile_updated": true,
  "lead_created": true,
  "lead_id": 456
}
```

**Логика**:
- Обновляет профиль (не перезаписывает, а дополняет — важно!)
- Создает сущность **Lead/Заявка** для панели тренера
- Устанавливает `ai_test_completed=True` в `TelegramUser`

### Поведение при входе

#### Сценарий 1: Новый пользователь из WebApp (без теста)
1. Пользователь открывает WebApp
2. WebApp отправляет `initData` на `/api/v1/webapp/auth/`
3. Backend:
   - Валидирует `initData`
   - Создает `User` + `TelegramUser` + `Profile` (пустой)
   - Возвращает `is_complete=false`
4. WebApp видит `is_complete=false` → запускает онбординг (3-5 экранов)
5. Пользователь заполняет: пол, возраст, рост, вес, цель
6. WebApp отправляет `PATCH /api/v1/profile/` с данными
7. Backend обновляет профиль → создает `DailyGoal` (auto-calculated)
8. WebApp переходит в рабочий режим (цели, дневник)

#### Сценарий 2: Старый пользователь (прошел тест в боте)
1. Пользователь открывает WebApp
2. WebApp отправляет `initData` на `/api/v1/webapp/auth/`
3. Backend:
   - Находит пользователя по `telegram_id`
   - Профиль уже заполнен (тест был пройден ранее)
   - Возвращает `is_complete=true` + goals
4. WebApp сразу показывает дневник и цели

#### Сценарий 3: Пользователь сначала в WebApp, потом прошел тест
1. Пользователь проходит онбординг в WebApp (минимальный профиль создан)
2. Позже проходит полный тест в боте
3. Бот отправляет `POST /api/v1/survey/apply/`
4. Backend:
   - Обновляет профиль (дополняет данные, не перезаписывает базовые поля)
   - Добавляет расширенные поля (training_level, goals, health_restrictions и т.д.)
   - Создает Lead/Заявку для тренера
5. При следующем открытии WebApp пользователь видит обогащенный профиль

### Панель тренера
**Источник данных**: Django models (`TelegramUser`, `Profile`, `DailyGoal`)

**Разделы**:
1. **Заявки (Applications)**: `TelegramUser.objects.filter(ai_test_completed=True, is_client=False)`
   - Показывает пользователей, прошедших тест, но еще не добавленных в клиенты
2. **Клиенты (Clients)**: `TelegramUser.objects.filter(is_client=True)`
   - Пользователи, добавленные тренером в работу

**Действия тренера**:
- Просмотр профиля + результатов теста
- Добавление в клиенты (устанавливает `is_client=True`)
- Назначение плана питания/тренировок (через AI или вручную)

---

## 4. Этапы внедрения (Roadmap)

### Этап 1: Аудит текущих моделей и API ✅ (DONE)

**Цель**: Понять текущую структуру данных и выявить конфликты/дублирование.

**Затрагиваемые файлы**:
- `backend/apps/users/models.py`
- `backend/apps/telegram/models.py`
- `backend/apps/nutrition/models.py`
- `bot/app/models/user.py`, `bot/app/models/survey.py`
- `backend/apps/telegram/views.py`
- `bot/app/services/django_integration.py`

**Критерии готовности**:
- ✅ Документированы все модели и их связи
- ✅ Выявлены дублирующиеся поля между `Profile` и `TelegramUser`
- ✅ Понятна текущая логика `save_test_results`

---

### Этап 2: Дизайн и реализация унифицированного endpoint `/api/v1/webapp/auth/`

**Цель**: Создать единый endpoint для авторизации WebApp, который возвращает полную информацию о пользователе и состоянии профиля.

**Затрагиваемые файлы**:
- `backend/apps/telegram/views.py` (новый view `webapp_auth`)
- `backend/apps/telegram/urls.py` (добавить route)
- `backend/apps/telegram/serializers.py` (новые serializers)
- `frontend/src/services/api.ts` (обновить метод `authenticate`)

**Задачи**:
1. Создать serializer для ответа:
   ```python
   class WebAppAuthResponseSerializer(serializers.Serializer):
       user = TelegramUserSerializer()
       profile = ProfileSerializer()
       goals = DailyGoalSerializer(allow_null=True)
       is_admin = serializers.BooleanField()
   ```

2. Создать view `webapp_auth`:
   - Валидировать `initData` через `TelegramWebAppAuthentication`
   - Получить или создать пользователя
   - Проверить полноту профиля (`is_complete`)
   - Вернуть профиль + цели + флаг is_admin

3. Добавить свойство `is_complete` в модель `Profile`:
   ```python
   @property
   def is_complete(self):
       return all([
           self.gender,
           self.birth_date,
           self.height,
           self.weight,
           self.goal_type
       ])
   ```

4. Обновить `frontend/src/services/api.ts`:
   - Метод `authenticate()` должен вызывать `/api/v1/webapp/auth/`
   - Сохранять `user`, `profile`, `goals` в контекст

**Риски**:
- Breaking change для существующего кода, если WebApp уже использует `/api/v1/telegram/auth/`
- Решение: сохранить старый endpoint для совместимости, но новый код использует `/api/v1/webapp/auth/`

**Критерии готовности**:
- ✅ Endpoint `/api/v1/webapp/auth/` работает
- ✅ Возвращает корректный JSON с `is_complete`
- ✅ WebApp успешно авторизуется и получает профиль

---

### Этап 3: Реализация endpoint `/api/v1/profile/` (GET/PATCH)

**Цель**: Позволить WebApp читать и обновлять профиль пользователя.

**Затрагиваемые файлы**:
- `backend/apps/users/views.py` (обновить `ProfileView`)
- `backend/apps/users/serializers.py` (обновить `ProfileSerializer`)
- `frontend/src/services/api.ts` (добавить `updateProfile`)

**Задачи**:
1. Обновить `ProfileSerializer`:
   - Включить все поля для онбординга: `gender`, `birth_date`, `height`, `weight`, `goal_type`, `activity_level`, `timezone`
   - Добавить `age` (read-only, computed)
   - Добавить `is_complete` (read-only)

2. Обновить `ProfileView`:
   - `GET`: вернуть профиль текущего пользователя
   - `PATCH`: обновить профиль (partial update)
   - Валидация: проверить корректность полей (возраст 14-80, рост 120-250, вес 30-300)

3. Добавить в `frontend/src/services/api.ts`:
   ```typescript
   async updateProfile(data: ProfileData) {
       const response = await fetchWithRetry(`${API_BASE}/profile/`, {
           method: 'PATCH',
           headers: getHeaders(),
           body: JSON.stringify(data)
       });
       if (!response.ok) throw new Error('Failed to update profile');
       return response.json();
   }
   ```

**Риски**:
- Конфликт с существующим endpoint `/api/v1/users/profile/`
- Решение: использовать существующий endpoint, но обновить его логику

**Критерии готовности**:
- ✅ `GET /api/v1/profile/` возвращает полный профиль
- ✅ `PATCH /api/v1/profile/` обновляет профиль
- ✅ Валидация работает корректно

---

### Этап 4: Реализация онбординга в WebApp (клиентская часть)

**Цель**: Создать микро-мастер в WebApp для первичного заполнения профиля.

**Затрагиваемые файлы**:
- `frontend/src/components/OnboardingFlow.tsx` (новый компонент)
- `frontend/src/contexts/AuthContext.tsx` (добавить проверку `is_complete`)
- `frontend/src/App.tsx` (маршрутизация к онбордингу)

**Задачи**:
1. Создать компонент `OnboardingFlow`:
   - Экран 1: Выбор пола (M/F)
   - Экран 2: Возраст (или дата рождения)
   - Экран 3: Рост (см)
   - Экран 4: Вес (кг)
   - Экран 5: Цель (похудение/поддержание/набор)
   - Кнопка "Далее" → переход к следующему экрану
   - Кнопка "Готово" → отправка на backend

2. Логика отправки:
   ```typescript
   const handleComplete = async () => {
       const profileData = {
           gender: onboardingData.gender,
           birth_date: calculateBirthDate(onboardingData.age),
           height: onboardingData.height,
           weight: onboardingData.weight,
           goal_type: onboardingData.goal_type
       };
       await api.updateProfile(profileData);
       // Redirect to main app
       navigate('/');
   };
   ```

3. Обновить `AuthContext`:
   - После аутентификации проверять `profile.is_complete`
   - Если `false` → редирект на `/onboarding`

4. Стилизация:
   - Использовать современный дизайн (Telegram WebApp стиль)
   - Прогресс-бар (1/5, 2/5, ...)
   - Валидация на клиенте (например, возраст 14-80)

**Риски**:
- UX: онбординг может быть навязчивым
- Решение: добавить кнопку "Пропустить" для заполнения профиля позже (но с ограничением функционала)

**Критерии готовности**:
- ✅ Онбординг отображается при `is_complete=false`
- ✅ Пользователь проходит все экраны
- ✅ Данные отправляются на backend и сохраняются
- ✅ После завершения редирект на главный экран

---

### Этап 5: Обновление логики бота (отправка в backend вместо SQLAlchemy)

**Цель**: Бот перестает записывать данные в свои таблицы, а отправляет все в Django.

**Затрагиваемые файлы**:
- `bot/app/services/django_integration.py` (обновить `send_test_results_to_django`)
- `bot/app/handlers/survey/confirmation.py` (обновить логику после завершения теста)
- `backend/apps/telegram/views.py` (обновить `save_test_results`)

**Задачи**:
1. **Обновить `send_test_results_to_django`**:
   - Убедиться, что маппинг полей корректен (age → birth_date, activity, goal)
   - Отправлять все данные теста в одном запросе

2. **Обновить `save_test_results` в Django**:
   - При получении данных теста:
     - Если пользователь существует → обновить профиль (дополнить, не перезаписать базовые поля)
     - Если пользователь новый → создать полный профиль
   - Создать сущность **Lead** (новая модель или флаг в `TelegramUser`)
   - Рассчитать и установить `DailyGoal`

3. **Логика обновления профиля**:
   ```python
   # Базовые поля обновляем только если они пусты
   if not profile.gender:
       profile.gender = test_data['gender']
   if not profile.birth_date:
       profile.birth_date = calculate_birth_date(test_data['age'])
   # И т.д.

   # Расширенные поля перезаписываем всегда
   profile.training_level = test_data['training_level']
   profile.goals = test_data['goals']
   profile.health_restrictions = test_data['health_restrictions']
   profile.current_body_type = test_data['current_body_type']
   profile.ideal_body_type = test_data['ideal_body_type']
   ```

4. **Создать модель `Lead`** (опционально, или использовать флаг `is_lead` в `TelegramUser`):
   ```python
   class Lead(models.Model):
       telegram_user = models.OneToOneField(TelegramUser, on_delete=models.CASCADE)
       created_at = models.DateTimeField(auto_now_add=True)
       status = models.CharField(max_length=20, choices=[
           ('new', 'Новая'),
           ('viewed', 'Просмотрена'),
           ('contacted', 'Связались'),
           ('converted', 'Стал клиентом')
       ], default='new')
   ```

5. **Отключить запись в SQLAlchemy** (временно закомментировать):
   - В `bot/app/handlers/survey/confirmation.py` закомментировать создание `SurveyAnswer`
   - Оставить только вызов `send_test_results_to_django()`

**Риски**:
- Потеря данных, если Django API недоступен
- Решение: сохранить retry-логику (уже есть в `django_integration.py`)
- Fallback: если Django недоступен, сохранить в SQLAlchemy как backup

**Критерии готовности**:
- ✅ Бот отправляет результаты теста в Django
- ✅ Django корректно обновляет профиль
- ✅ Создается Lead/Заявка для тренера
- ✅ Не создаются дублирующие записи в SQLAlchemy

---

### Этап 6: Обновление панели тренера (чтение из Django)

**Цель**: Панель тренера читает данные заявок и клиентов из Django, а не из SQLAlchemy-таблиц бота.

**Затрагиваемые файлы**:
- `backend/apps/telegram/views.py` (endpoints `/api/v1/telegram/applications/`, `/api/v1/telegram/clients/`)
- `frontend/src/pages/TrainerPanelPage.tsx` (обновить отображение данных)

**Задачи**:
1. **Обновить endpoint `/api/v1/telegram/applications/`**:
   - Возвращать `TelegramUser.objects.filter(ai_test_completed=True, is_client=False)`
   - Включить данные профиля (через join с `Profile`)
   - Serializer:
     ```python
     class ApplicationSerializer(serializers.ModelSerializer):
         profile = ProfileSerializer(source='user.profile')
         recommended_goals = DailyGoalSerializer(source='user.daily_goals.filter(is_active=True).first')

         class Meta:
             model = TelegramUser
             fields = ['id', 'telegram_id', 'first_name', 'last_name', 'username',
                       'display_name', 'ai_test_completed', 'profile', 'recommended_goals',
                       'created_at']
     ```

2. **Обновить endpoint `/api/v1/telegram/clients/`**:
   - Возвращать `TelegramUser.objects.filter(is_client=True)`
   - Аналогичная структура serializer

3. **Добавить endpoint для добавления в клиенты**:
   ```python
   @api_view(['POST'])
   def add_to_clients(request, telegram_user_id):
       telegram_user = TelegramUser.objects.get(id=telegram_user_id)
       telegram_user.is_client = True
       telegram_user.save()
       return Response({'status': 'success'})
   ```

4. **Обновить frontend**:
   - Убедиться, что отображаются данные из нового формата
   - Добавить кнопку "Добавить в клиенты" в карточке заявки

**Риски**:
- Переход на новый формат данных может сломать существующий UI
- Решение: постепенная миграция, сохранить старые endpoints для совместимости

**Критерии готовности**:
- ✅ Панель тренера показывает заявки из Django
- ✅ Можно добавить заявку в клиенты
- ✅ Данные профиля корректно отображаются

---

### Этап 7: Создание endpoint `/api/v1/profile/complete-onboarding/`

**Цель**: Упростить онбординг — один запрос для сохранения всех данных.

**Затрагиваемые файлы**:
- `backend/apps/users/views.py` (новый view)
- `backend/apps/users/urls.py` (добавить route)
- `frontend/src/components/OnboardingFlow.tsx` (использовать новый endpoint)

**Задачи**:
1. Создать view `complete_onboarding`:
   ```python
   @api_view(['POST'])
   @permission_classes([IsAuthenticated])
   def complete_onboarding(request):
       profile = request.user.profile
       serializer = ProfileSerializer(profile, data=request.data, partial=True)
       if serializer.is_valid():
           serializer.save()
           # Автоматически создать DailyGoal
           try:
               goals = DailyGoal.calculate_goals(request.user)
               DailyGoal.objects.create(
                   user=request.user,
                   calories=goals['calories'],
                   protein=goals['protein'],
                   fat=goals['fat'],
                   carbohydrates=goals['carbohydrates'],
                   source='AUTO',
                   is_active=True
               )
           except Exception as e:
               logger.error(f"Failed to calculate goals: {e}")
           return Response(serializer.data)
       return Response(serializer.errors, status=400)
   ```

2. Обновить frontend:
   ```typescript
   const handleComplete = async () => {
       await api.completeOnboarding(onboardingData);
       navigate('/');
   };
   ```

**Критерии готовности**:
- ✅ Endpoint работает
- ✅ Профиль сохраняется и `is_complete` становится `true`
- ✅ Автоматически создается `DailyGoal`

---

### Этап 8: Миграция и архивация старых таблиц бота

**Цель**: Отключить использование SQLAlchemy-таблиц бота, оставить их как архив.

**Затрагиваемые файлы**:
- `bot/app/models/user.py`, `bot/app/models/survey.py`
- `bot/app/handlers/**/*.py` (убрать все записи в SQLAlchemy)

**Задачи**:
1. **Аудит использования SQLAlchemy**:
   - Найти все места, где создаются/обновляются `User`, `SurveyAnswer`, `Plan`
   - Закомментировать или удалить эти вызовы

2. **Создать скрипт миграции данных** (опционально):
   - Если есть старые пользователи в SQLAlchemy → перенести в Django
   - Скрипт: `bot/scripts/migrate_to_django.py`

3. **Обновить документацию**:
   - Указать, что SQLAlchemy-таблицы больше не используются
   - Документировать новый flow (бот → Django API)

**Риски**:
- Потеря исторических данных из SQLAlchemy
- Решение: оставить таблицы как есть, но не использовать для новых пользователей

**Критерии готовности**:
- ✅ Бот не создает новые записи в SQLAlchemy
- ✅ Все данные записываются в Django
- ✅ Старые таблицы остаются для архивных данных

---

### Этап 9: Интеграция с панелью тренера — назначение AI-планов

**Цель**: Тренер может назначать AI-планы питания/тренировок через панель.

**Затрагиваемые файлы**:
- `backend/apps/users/models.py` (добавить поля в `Profile`)
- `backend/apps/telegram/views.py` (новые endpoints для назначения плана)
- `frontend/src/pages/TrainerPanelPage.tsx` (UI для назначения плана)

**Задачи**:
1. **Добавить поля в `Profile`**:
   - `assigned_plan` (TextField, nullable) — текст плана от тренера
   - `plan_assigned_at` (DateTimeField, nullable)
   - `plan_assigned_by` (FK to User, nullable) — кто назначил

2. **Создать endpoint `/api/v1/telegram/assign-plan/`**:
   ```python
   @api_view(['POST'])
   @permission_classes([TelegramAdminPermission])
   def assign_plan(request, telegram_user_id):
       telegram_user = TelegramUser.objects.get(id=telegram_user_id)
       profile = telegram_user.user.profile
       profile.assigned_plan = request.data['plan']
       profile.plan_assigned_at = timezone.now()
       profile.plan_assigned_by = request.user
       profile.save()
       # Отправить уведомление пользователю в Telegram (опционально)
       return Response({'status': 'success'})
   ```

3. **Добавить UI в панель тренера**:
   - Кнопка "Назначить план" в карточке клиента
   - Модальное окно с текстовым полем для ввода плана
   - После назначения → уведомление "План назначен"

**Критерии готовности**:
- ✅ Тренер может назначить план клиенту
- ✅ План сохраняется в профиле
- ✅ (Опционально) Клиент получает уведомление в Telegram

---

## 5. Onboarding Flow (микро-мастер в WebApp)

### Условие запуска
При авторизации через `/api/v1/webapp/auth/`:
- Если `profile.is_complete === false` → запустить онбординг
- Если `profile.is_complete === true` → перейти в основной интерфейс

### Экраны онбординга

#### Экран 1: Пол
**Вопрос**: "Укажите ваш пол"
**Варианты**:
- Мужской (M)
- Женский (F)

**UI**: Две крупные кнопки с иконками

#### Экран 2: Возраст
**Вопрос**: "Сколько вам лет?"
**Ввод**: Числовое поле (14-80)
**Валидация**: возраст должен быть в диапазоне 14-80

#### Экран 3: Рост
**Вопрос**: "Ваш рост?"
**Ввод**: Числовое поле + "см" (120-250)
**Валидация**: рост должен быть в диапазоне 120-250

#### Экран 4: Вес
**Вопрос**: "Ваш текущий вес?"
**Ввод**: Числовое поле + "кг" (30-300)
**Валидация**: вес должен быть в диапазоне 30-300

#### Экран 5: Цель
**Вопрос**: "Какая ваша цель?"
**Варианты**:
- Похудение (weight_loss)
- Поддержание веса (maintenance)
- Набор массы (weight_gain)

**UI**: Три карточки с описанием

#### Экран 6: Завершение
**Текст**: "Отлично! Мы рассчитали ваши цели по питанию"
**Кнопка**: "Начать использовать приложение"

### Запросы на backend

После завершения онбординга:
```typescript
// 1. Сохранить профиль
await api.completeOnboarding({
    gender: 'M',
    birth_date: '1990-01-01',  // вычисляется из возраста
    height: 180,
    weight: 80,
    goal_type: 'weight_loss',
    activity_level: 'sedentary'  // default
});

// 2. Перезагрузить профиль и цели
const profile = await api.getProfile();
const goals = await api.getDailyGoals();

// 3. Редирект на главную страницу
navigate('/');
```

### Опциональная функция: "Пропустить"
- Кнопка "Пропустить онбординг" на каждом экране
- При пропуске: сохранить только уже введенные данные
- Профиль останется `is_complete=false`
- В основном интерфейсе показывать баннер: "Завершите профиль для точного расчета целей"

---

## 6. Интеграция с ботом (survey / лид-магнит)

### Endpoint: `/api/v1/survey/apply/`

**Метод**: `POST`
**Body**:
```json
{
  "telegram_id": 987654321,
  "first_name": "John",
  "last_name": "Doe",
  "username": "john_doe",
  "answers": {
    "gender": "male",
    "age": 30,
    "height": 180,
    "weight": 80,
    "goal": "fat_loss",
    "activity_level": "medium",
    "training_level": "intermediate",
    "goals": ["weight_loss", "muscle_tone"],
    "health_restrictions": ["none"],
    "current_body_type": 2,
    "ideal_body_type": 3,
    "timezone": "Europe/Moscow"
  }
}
```

### Логика обработки

#### 1. Найти или создать пользователя
```python
telegram_user, created = TelegramUser.objects.get_or_create(
    telegram_id=data['telegram_id'],
    defaults={
        'first_name': data['first_name'],
        'last_name': data['last_name'],
        'username': data['username']
    }
)
user = telegram_user.user
```

#### 2. Обновить профиль (умное обновление)
```python
profile = user.profile

# Базовые поля — обновляем только если пусты
if not profile.gender:
    profile.gender = map_gender(answers['gender'])
if not profile.birth_date:
    profile.birth_date = calculate_birth_date(answers['age'])
if not profile.height:
    profile.height = answers['height']
if not profile.weight:
    profile.weight = answers['weight']
if not profile.goal_type:
    profile.goal_type = map_goal(answers['goal'])

# Расширенные поля — перезаписываем всегда
profile.activity_level = map_activity(answers['activity_level'])
profile.training_level = answers['training_level']
profile.goals = answers['goals']
profile.health_restrictions = answers['health_restrictions']
profile.current_body_type = answers['current_body_type']
profile.ideal_body_type = answers['ideal_body_type']
profile.timezone = answers['timezone']

profile.save()
```

#### 3. Создать Lead
```python
telegram_user.ai_test_completed = True
telegram_user.ai_test_answers = answers
telegram_user.save()

# Опционально: создать отдельную сущность Lead
# Lead.objects.create(telegram_user=telegram_user, status='new')
```

#### 4. Рассчитать и установить DailyGoal
```python
# Деактивировать старые цели
DailyGoal.objects.filter(user=user, is_active=True).update(is_active=False)

# Рассчитать новую цель
goals = DailyGoal.calculate_goals(user)

# Создать новую активную цель
DailyGoal.objects.create(
    user=user,
    calories=goals['calories'],
    protein=goals['protein'],
    fat=goals['fat'],
    carbohydrates=goals['carbohydrates'],
    source='AUTO',
    is_active=True
)
```

### Маппинг значений

#### Gender
- `"male"` → `"M"`
- `"female"` → `"F"`

#### Activity Level
- `"minimal"` → `"sedentary"`
- `"low"` → `"lightly_active"`
- `"medium"` → `"moderately_active"`
- `"high"` → `"very_active"`

#### Goal
- `"fat_loss"` → `"weight_loss"`
- `"muscle_gain"` → `"weight_gain"`
- `"maintenance"` → `"maintenance"`

### Отправка из бота
В `bot/app/handlers/survey/confirmation.py`:
```python
await send_test_results_to_django(
    telegram_id=user.tg_id,
    first_name=user.full_name.split()[0],
    last_name=user.full_name.split()[1] if len(user.full_name.split()) > 1 else "",
    username=user.username,
    survey_data={
        "gender": survey.gender,
        "age": survey.age,
        "height_cm": survey.height_cm,
        "weight_kg": survey.weight_kg,
        "goal": survey.goal,
        "activity": survey.activity,
        "training_level": survey.training_level,
        "body_goals": survey.body_goals,
        "health_limitations": survey.health_limitations,
        "body_now_id": survey.body_now_id,
        "body_ideal_id": survey.body_ideal_id,
        "tz": survey.tz
    }
)
```

---

## 7. Migration & Compatibility

### Обратная совместимость

#### Старые endpoints
Сохранить для совместимости:
- `POST /api/v1/telegram/auth/` — для старых клиентов WebApp
- `POST /api/v1/telegram/save-test/` — для старой версии бота

#### Новые endpoints
Постепенно мигрировать на:
- `POST /api/v1/webapp/auth/` — для новых клиентов WebApp
- `POST /api/v1/survey/apply/` — для новой версии бота

### Обработка частично заполненных профилей

#### Сценарий: Профиль был создан через WebApp, но без онбординга
- `Profile` существует, но `is_complete=false`
- При входе в WebApp → запустить онбординг
- После завершения онбординга → `is_complete=true`

#### Сценарий: Профиль был создан через тест в боте
- `Profile` существует, `is_complete=true`
- При входе в WebApp → сразу рабочий интерфейс
- Пользователь может редактировать профиль через настройки

#### Сценарий: Пользователь сначала прошел онбординг, потом тест
- Онбординг заполнил минимальные поля
- Тест дополнил профиль расширенными полями
- Базовые поля (пол, возраст, рост, вес) не перезаписываются
- Расширенные поля (training_level, goals, health_restrictions) обновляются

### Что делать со старыми таблицами бота?

#### Опция 1: Оставить как архив (рекомендуется)
- Не удалять таблицы `users`, `survey_answers`, `plans`
- Не создавать новые записи
- Использовать только для чтения старых данных

#### Опция 2: Создать скрипт миграции
Если нужно перенести старые данные в Django:
```python
# bot/scripts/migrate_to_django.py
async def migrate_users():
    async with get_session() as session:
        users = await session.execute(select(User))
        for user in users.scalars():
            # Создать Django User + Profile
            django_user, created = User.objects.get_or_create(
                username=f"tg_{user.tg_id}",
                defaults={
                    'first_name': user.full_name.split()[0],
                    'last_name': user.full_name.split()[1] if len(user.full_name.split()) > 1 else ""
                }
            )
            TelegramUser.objects.get_or_create(
                telegram_id=user.tg_id,
                user=django_user
            )
```

**Решение**: Оставить таблицы как архив, новая логика использует только Django.

---

## 8. Testing Plan

### Сценарии тестирования

#### Тест 1: Новый пользователь → онбординг в WebApp
**Шаги**:
1. Открыть WebApp в Telegram (первый раз)
2. Пройти авторизацию через `initData`
3. Увидеть экран онбординга
4. Заполнить все поля (пол, возраст, рост, вес, цель)
5. Нажать "Завершить"

**Ожидаемый результат**:
- Профиль создан в Django
- `is_complete=true`
- `DailyGoal` создан (auto-calculated)
- Редирект на главный экран (дневник/цели)

**Проверка в БД**:
```sql
SELECT * FROM users_profile WHERE telegram_id = 987654321;
SELECT * FROM nutrition_daily_goals WHERE user_id = (SELECT id FROM auth_user WHERE username = 'tg_987654321');
```

---

#### Тест 2: Новый пользователь → сначала тест в боте, потом WebApp
**Шаги**:
1. Пройти тест в боте (команда `/start`)
2. Завершить тест
3. Открыть WebApp в Telegram

**Ожидаемый результат**:
- Профиль создан в Django (из бота)
- `is_complete=true`
- WebApp показывает главный экран (без онбординга)
- Цели и дневник работают корректно

**Проверка в БД**:
```sql
SELECT * FROM users_profile WHERE telegram_id = 987654321;
SELECT * FROM telegram_telegramuser WHERE telegram_id = 987654321 AND ai_test_completed = true;
```

---

#### Тест 3: Пользователь сначала в WebApp, потом прошел тест
**Шаги**:
1. Открыть WebApp, пройти онбординг
2. Использовать приложение (добавить прием пищи)
3. Позже пройти тест в боте

**Ожидаемый результат**:
- Профиль обновлен (дополнен данными из теста)
- Базовые поля (пол, возраст, рост, вес) не изменились
- Добавлены расширенные поля (training_level, goals, health_restrictions)
- Заявка создана для тренера (`ai_test_completed=true`)

**Проверка в БД**:
```sql
-- Проверить, что базовые поля не изменились
SELECT gender, birth_date, height, weight FROM users_profile WHERE telegram_id = 987654321;

-- Проверить, что добавились расширенные поля
SELECT training_level, goals, health_restrictions FROM users_profile WHERE telegram_id = 987654321;

-- Проверить, что создана заявка
SELECT * FROM telegram_telegramuser WHERE telegram_id = 987654321 AND ai_test_completed = true;
```

---

#### Тест 4: Обновление целей КБЖУ в WebApp
**Шаги**:
1. Авторизоваться в WebApp
2. Перейти в раздел "Профиль"
3. Нажать "Редактировать цели"
4. Изменить значения (белки/жиры/углеводы)
5. Сохранить

**Ожидаемый результат**:
- Цели обновлены в БД
- `source='MANUAL'`
- `is_active=true`
- Старые цели деактивированы (`is_active=false`)

**Проверка в БД**:
```sql
SELECT * FROM nutrition_daily_goals WHERE user_id = (SELECT id FROM auth_user WHERE username = 'tg_987654321') ORDER BY created_at DESC;
```

---

#### Тест 5: Панель тренера — просмотр заявок
**Шаги**:
1. Авторизоваться в панели тренера (админ WebApp)
2. Перейти в раздел "Заявки"
3. Увидеть список пользователей, прошедших тест

**Ожидаемый результат**:
- Список заявок из Django (`TelegramUser` с `ai_test_completed=true`)
- Каждая заявка содержит: имя, Telegram ID, КБЖУ, дату теста

**Проверка API**:
```bash
curl -X GET https://api.foodmind.ru/api/v1/telegram/applications/ \
  -H "X-Telegram-Init-Data: <admin_init_data>"
```

---

#### Тест 6: Панель тренера — добавить в клиенты
**Шаги**:
1. В панели тренера выбрать заявку
2. Нажать "Добавить в клиенты"

**Ожидаемый результат**:
- `is_client=true` для этого пользователя
- Заявка исчезает из списка "Заявки"
- Заявка появляется в списке "Клиенты"

**Проверка в БД**:
```sql
UPDATE telegram_telegramuser SET is_client = true WHERE id = 123;
SELECT * FROM telegram_telegramuser WHERE is_client = true;
```

---

#### Тест 7: Ошибка при сохранении целей (401/403)
**Шаги**:
1. Открыть WebApp, но изменить `initData` (подделать подпись)
2. Попытаться сохранить цели

**Ожидаемый результат**:
- Ошибка 401 Unauthorized
- Сообщение: "Не авторизован. Откройте приложение через Telegram бота заново."

---

#### Тест 8: Пропуск онбординга
**Шаги**:
1. Открыть WebApp (первый раз)
2. На экране онбординга нажать "Пропустить"

**Ожидаемый результат**:
- Профиль остается `is_complete=false`
- Редирект на главный экран
- Показывается баннер: "Завершите профиль для точного расчета целей"
- Функционал ограничен (например, нельзя рассчитать цели автоматически)

---

## 9. Дополнительные улучшения (post-MVP)

### 9.1. Расширенный онбординг
- Добавить вопросы об уровне активности
- Добавить вопрос о целевом весе
- Добавить вопрос о пищевых предпочтениях (вегетарианство, аллергии)

### 9.2. AI-рекомендации в профиле
- После завершения онбординга: показывать AI-рекомендации на основе профиля
- Хранить в `Profile.ai_recommendations` (JSON)

### 9.3. Синхронизация часового пояса
- Автоматически определять часовой пояс из Telegram WebApp
- Сохранять в `Profile.timezone`

### 9.4. История изменений профиля
- Создать модель `ProfileHistory` для отслеживания изменений веса/целей
- Показывать график прогресса в WebApp

### 9.5. Уведомления о новых заявках
- При создании Lead отправлять уведомление тренеру в Telegram
- Использовать Telegram Bot API

### 9.6. Экспорт данных пользователя
- Endpoint для экспорта профиля и дневника в JSON/CSV
- GDPR compliance

---

## 10. Summary & Next Steps

### Что мы получим после внедрения
1. **Единый профиль**: все данные пользователя в Django, привязаны к `telegram_id`
2. **WebApp-first**: новые пользователи могут работать без теста в боте
3. **Онбординг**: быстрая регистрация (3-5 экранов) в WebApp
4. **Тест как расширение**: опрос в боте дополняет профиль и создает Lead
5. **Панель тренера**: читает заявки и клиентов из Django

### Порядок выполнения
1. **Этап 2**: Создать `/api/v1/webapp/auth/` (1-2 дня)
2. **Этап 3**: Обновить `/api/v1/profile/` (1 день)
3. **Этап 4**: Реализовать онбординг в WebApp (2-3 дня)
4. **Этап 5**: Обновить логику бота (1-2 дня)
5. **Этап 6**: Обновить панель тренера (1 день)
6. **Этап 7**: Создать `/api/v1/profile/complete-onboarding/` (1 день)
7. **Этап 8**: Миграция/архивация старых таблиц (1 день)

**Общий срок**: 2-3 недели (при работе в одиночку).

### Критические точки
- **Не сломать существующих пользователей**: сохранить старые endpoints для совместимости
- **Тестирование**: обязательно протестировать все 8 сценариев
- **Данные**: не потерять данные при миграции (backup перед началом работ)

### Контакты для вопросов
- Backend: `backend/apps/users/`, `backend/apps/telegram/`, `backend/apps/nutrition/`
- Bot: `bot/app/models/`, `bot/app/services/django_integration.py`
- Frontend: `frontend/src/services/api.ts`, `frontend/src/contexts/AuthContext.tsx`
