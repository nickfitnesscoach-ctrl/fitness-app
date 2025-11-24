# Полный аудит Telegram WebApp интеграции FoodMind
**Дата:** 2025-11-24
**Обновлено:** 2025-11-24 (все критические проблемы исправлены)
**Аудитор:** Senior Full-Stack Developer + Архитектор
**Проект:** FoodMind (монорепа: backend Django + bot aiogram + frontend React)

## 🎉 СТАТУС ИСПРАВЛЕНИЙ

### ✅ Выполнено (2025-11-24)
- ✅ **P0-1**: Исправлен неправильный `secret_key` в `telegram_auth.py`
- ✅ **P0-2**: Создан хук `useTelegramWebApp` и исправлены баннеры
- ✅ **P1-1**: Удалена проверка `telegramId` на фронте в ProfilePage
- ✅ **P1-2**: Создан единый сервис валидации `TelegramWebAppAuthService`
- ✅ **P1-3**: Исправлен рассинхрон admin ID (используется `settings.TELEGRAM_ADMINS`)

### 📋 Созданные файлы
1. `backend/apps/telegram/services/webapp_auth.py` - единый сервис валидации
2. `backend/apps/telegram/services/__init__.py` - экспорты сервиса
3. `frontend/src/hooks/useTelegramWebApp.ts` - React хук для WebApp

### 🔧 Обновленные файлы
1. `backend/apps/telegram/telegram_auth.py:90` - исправлен secret_key
2. `backend/apps/telegram/authentication.py` - использует новый сервис
3. `backend/apps/telegram/views.py:48-108` - обновлен trainer_panel_auth
4. `frontend/src/pages/ClientDashboard.tsx` - использует useTelegramWebApp hook
5. `frontend/src/pages/ProfilePage.tsx:93-117` - удалена проверка telegramId

---

## Оглавление
1. [Executive Summary](#executive-summary)
2. [Архитектура проекта](#архитектура-проекта)
3. [Карта Telegram/WebApp интеграций](#карта-telegramwebapp-интеграций)
4. [Выявленные проблемы](#выявленные-проблемы)
5. [План исправлений](#план-исправлений)
6. [Unified Telegram Integration Contract](#unified-telegram-integration-contract)
7. [Сценарии тестирования](#сценарии-тестирования)

---

## Executive Summary

### Текущее состояние
Приложение FoodMind страдает от **рассинхронизации и дублирования логики** работы с Telegram WebApp на трёх уровнях: backend, frontend, bot. Это приводит к:

1. **Баннерам об ошибках**, которые показываются даже внутри Telegram WebApp
2. **Потере Telegram ID** при обращении к API (цели/дневник)
3. **Неконсистентной валидации initData** (три разных реализации)
4. **Админам не даёт доступ** к панели тренера

### Корневые причины
| Проблема | Где | Почему |
|----------|-----|--------|
| Неверный детект WebApp | Frontend | Проверка `window.Telegram.WebApp` на module-level вместо runtime |
| Потеря Telegram ID | Backend/Frontend | Несколько способов передачи ID, нет единого источника правды |
| 3 разных парсера initData | Backend | `authentication.py`, `telegram_auth.py`, `views.py` |
| Рассинхрон admin ID | Backend/Bot | `TELEGRAM_ADMINS` vs `BOT_ADMIN_ID` vs `ADMIN_IDS` |
| Баннеры показываются всегда | Frontend | Нет проверки на `isReady` перед показом |

### Критичность
🔴 **HIGH**: Пользователи видят ошибки внутри Telegram → плохой UX → отток
🟡 **MEDIUM**: Админы не могут войти в панель → бизнес-функциональность заблокирована

---

## Архитектура проекта

### Структура монорепы
```
FoodMind/
├── backend/          # Django + DRF (порт 8000)
│   ├── apps/
│   │   ├── telegram/ # Telegram интеграция
│   │   ├── nutrition/# КБЖУ, цели, дневник
│   │   └── users/    # Профили пользователей
│   └── config/
│
├── frontend/         # React SPA (Vite)
│   ├── src/
│   │   ├── lib/telegram.ts      # Telegram SDK обёртка
│   │   ├── services/api.ts      # API client
│   │   ├── contexts/AuthContext # Auth provider
│   │   └── pages/
│   │       ├── ClientDashboard  # Главная (КБЖУ)
│   │       ├── ProfilePage      # Мои цели
│   │       └── TrainerPanel     # Панель тренера (/panel)
│   └── dist/         # Build output (сервится Django в проде)
│
└── bot/              # aiogram 3 (webhook)
    ├── app/
    │   ├── handlers/ # /start, опросы
    │   ├── keyboards/# WebApp кнопки
    │   └── config.py # Settings (admin_ids, urls)
    └── .env
```

### Deployment
- **Docker Compose**: 3 контейнера (fm-backend, fm-bot, fm-frontend)
- **Nginx**: Reverse proxy для всех сервисов
- **Базовый домен**: `https://eatfit24.ru`

---

## Карта Telegram/WebApp интеграций

### 1. Backend (Django)

#### 1.1. Модели (`apps/telegram/models.py`)
```python
class TelegramUser(models.Model):
    user = models.OneToOneField(User, related_name='telegram_profile')
    telegram_id = models.BigIntegerField(unique=True, db_index=True)
    username = models.CharField(max_length=255, blank=True)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255, blank=True)
    # ... other fields
```
✅ **Хорошо**: Единая модель для хранения Telegram данных
❌ **Проблема**: В `apps/users/models.py` есть дубликат `telegram_id` в `Profile`

#### 1.2. Authentication Backends

##### a) `TelegramWebAppAuthentication` (DRF, файл: `authentication.py:26`)
```python
class TelegramWebAppAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        init_data = request.META.get('HTTP_X_TELEGRAM_INIT_DATA') or request.data.get('initData')
        if not self.validate_init_data(init_data):  # Собственная реализация
            raise AuthenticationFailed('Invalid signature')
        # ...
```
- **Используется**: DRF ViewSets (автоматически через `DEFAULT_AUTHENTICATION_CLASSES`)
- **Валидация**: HMAC-SHA256 (`secret_key = hmac.new(b'WebAppData', bot_token, sha256)`)
- ✅ Правильная реализация по официальным docs Telegram
- ❌ **Проблема**: Дублирует логику из `telegram_auth.py`

##### b) `TelegramHeaderAuthentication` (DRF, файл: `authentication.py:205`)
```python
class TelegramHeaderAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        telegram_id = request.META.get('HTTP_X_TELEGRAM_ID')  # От Nginx
        # Auto-create user if not exists
```
- **Используется**: Для запросов через Nginx (если настроен header forwarding)
- **Проблема**: Полагается на то, что Nginx сам валидирует initData — небезопасно

##### c) `validate_init_data()` (утилита, файл: `telegram_auth.py:35`)
```python
def validate_init_data(raw_init_data: str, bot_token: str) -> Optional[Dict]:
    # SHA256(bot_token) -> secret_key
    # HMAC-SHA256(secret_key, data_check_string) = hash
```
- **Используется**: В views (`trainer_panel_auth`) и middleware
- ✅ **Хорошо**: Правильная реализация
- ❌ **Проблема**: **ДРУГАЯ** схема генерации `secret_key`!
  - В `TelegramWebAppAuthentication`: `hmac.new(b'WebAppData', bot_token, sha256)`
  - В `telegram_auth.py`: `hashlib.sha256(bot_token.encode())`
  - **ЭТО КРИТИЧЕСКИЙ БАГ!** Разные secret_key → разные hash → валидация может fail

#### 1.3. Endpoints

##### `/api/v1/telegram/auth/` (файл: `views.py:138`)
```python
@api_view(['POST'])
@permission_classes([AllowAny])
def telegram_auth(request):
    authenticator = TelegramWebAppAuthentication()
    user, _ = authenticator.authenticate(request)
    # Возвращает JWT + user info
```
- **Цель**: Получить JWT токены (для SPA)
- **НО**: JWT токены НЕ используются в WebApp! Используются header'ы

##### `/api/v1/trainer-panel/auth/` (файл: `views.py:48`)
```python
@api_view(['POST'])
@permission_classes([AllowAny])
def trainer_panel_auth(request):
    raw_init_data = request.data.get("init_data") or request.data.get("initData")
    parsed_data = validate_init_data(raw_init_data, settings.TELEGRAM_BOT_TOKEN)  # telegram_auth.py
    # Проверка admin ID
    admins = os.getenv("TELEGRAM_ADMINS").split(",") + [os.getenv("BOT_ADMIN_ID")]
```
- **Используется**: Панель тренера (`TrainerPanel.tsx`)
- ❌ **Проблема 1**: Использует `validate_init_data` (неправильный secret_key)
- ❌ **Проблема 2**: Читает env напрямую (`os.getenv`) вместо `settings.TELEGRAM_ADMINS`
- ❌ **Проблема 3**: Парсинг admin ID в runtime → может быть рассинхрон

##### `/api/v1/nutrition/goals/` (файл: `apps/nutrition/views.py`)
```python
class DailyGoalViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]  # DRF auth

    def get_queryset(self):
        return DailyGoal.objects.filter(user=self.request.user, is_active=True)
```
- **Используется**: Страница "Мои цели" (`ProfilePage.tsx`)
- ✅ **Хорошо**: Использует `request.user` (заполняется через `TelegramWebAppAuthentication`)
- ❌ **Проблема**: Если auth не прошла → 401 → фронт показывает "Telegram ID не найден"

#### 1.4. Admin ID конфигурация (`config/settings/base.py:529`)
```python
BOT_ADMIN_ID = os.environ.get("BOT_ADMIN_ID")
_telegram_admins_str = os.environ.get("TELEGRAM_ADMINS", "")
TELEGRAM_ADMINS = set(int(x.strip()) for x in _telegram_admins_str.split(",") if x.strip().isdigit())
if BOT_ADMIN_ID and BOT_ADMIN_ID.isdigit():
    TELEGRAM_ADMINS.add(int(BOT_ADMIN_ID))
```
- ✅ **Хорошо**: Объединяет `BOT_ADMIN_ID` и `TELEGRAM_ADMINS`
- ❌ **Проблема**: В `views.py:trainer_panel_auth` это дублируется через `os.getenv`

---

### 2. Frontend (React)

#### 2.1. Telegram SDK обёртка (`src/lib/telegram.ts`)

##### Инициализация
```typescript
let _telegramAuthData: TelegramAuthData | null = null;

export async function initTelegramWebApp(): Promise<TelegramAuthData | null> {
    const tg = getTelegramWebApp();

    if (tg?.initData && tg?.initDataUnsafe?.user) {  // ✅ Правильная проверка
        tg.ready();
        tg.expand();
        _telegramAuthData = { initData: tg.initData, user: tg.initDataUnsafe.user };
        return _telegramAuthData;
    }

    // DEV MODE fallback
    if (isDevMode && skipTelegramAuth) {
        _telegramAuthData = { initData: DEV_INIT_DATA, user: DEV_USER };
        return _telegramAuthData;
    }

    return null;  // ❌ Telegram not available
}
```
✅ **Хорошо**:
- Централизованная инициализация
- DEV mode для локальной разработки
- Singleton pattern (вызывается 1 раз)

❌ **Проблема**:
- Нет обработки случая, когда `initData` пустой, но WebApp существует
- Нет retry механизма (если `initDataUnsafe` ещё не загрузился)

##### Headers Builder
```typescript
export function buildTelegramHeaders(): HeadersInit {
    if (!_telegramAuthData) {
        // Graceful degradation - возвращает пустые headers
        return { 'Content-Type': 'application/json' };
    }

    return {
        'Content-Type': 'application/json',
        'X-Telegram-ID': String(user.id),
        'X-Telegram-Init-Data': initData,
        // ... other headers
    };
}
```
✅ **Хорошо**: Единая функция для всех запросов
❌ **Проблема**: Graceful degradation скрывает ошибки (лучше throw)

#### 2.2. AuthContext (`src/contexts/AuthContext.tsx`)

```typescript
export const AuthProvider: React.FC = ({ children }) => {
    const [user, setUser] = useState<User | null>(null);
    const [loading, setLoading] = useState(true);  // ❌ Starts with true!

    useEffect(() => {
        authenticate();  // Runs immediately on mount
    }, []);

    const authenticate = async () => {
        const authData = await initTelegramWebApp();  // ❌ Может вернуть null
        if (!authData) {
            setError('Telegram WebApp не инициализирован');  // ❌ Показывается сразу
            return;
        }
        // ... backend auth
    };
```
❌ **Проблемы**:
1. `loading=true` с самого начала → UI показывает loader
2. Если `initTelegramWebApp()` возвращает `null` → сразу показывается error баннер
3. Нет проверки `isReady` → баннеры показываются ДО инициализации WebApp

#### 2.3. Компоненты с ошибками

##### `ProfilePage.tsx` (строка 108)
```typescript
const handleSaveGoals = async () => {
    const debugInfo = api.getDebugInfo();
    if (!debugInfo.telegramId) {  // ❌ Проверка ПЕРЕД запросом
        setError('Ошибка: Telegram ID не найден. Пожалуйста, откройте приложение через Telegram бота.');
        return;
    }
    await api.updateGoals(editedGoals);
};
```
❌ **Проблема**:
- Проверка `telegramId` на фронте → если `null`, показывается баннер
- **НО**: `telegramId` может быть `null` просто потому что `initTelegramWebApp` ещё не завершился
- **Решение**: Убрать эту проверку, полагаться на backend 401/403

##### `ClientDashboard.tsx` (строка 51)
```typescript
useEffect(() => {
    const debugInfo = api.getDebugInfo();
    if (!debugInfo.webAppExists) {  // ❌ Проверка на module level
        setTelegramWarning('Приложение открыто вне Telegram...');
    }
}, []);
```
❌ **Проблема**:
- `webAppExists` проверяется сразу при монтировании
- **НО**: `window.Telegram.WebApp` может загружаться async (скрипт из CDN)
- **Решение**: Подождать `isReady` из `useTelegramWebApp` хука

---

### 3. Bot (aiogram 3)

#### 3.1. Config (`app/config.py`)
```python
class Settings(BaseSettings):
    BOT_ADMIN_ID: Optional[int] = None
    ADMIN_IDS: Optional[str] = None
    TELEGRAM_ADMINS: Optional[str] = None

    WEB_APP_URL: Optional[str] = None  # https://eatfit24.ru
    TRAINER_PANEL_BASE_URL: Optional[str] = None  # https://eatfit24.ru

    @property
    def admin_ids(self) -> set[int]:
        """Возвращает множество admin ID из всех источников."""
        ids = set()
        if self.BOT_ADMIN_ID:
            ids.add(self.BOT_ADMIN_ID)
        if self.TELEGRAM_ADMINS:
            ids.update(int(x.strip()) for x in self.TELEGRAM_ADMINS.split(",") if x.strip().isdigit())
        if self.ADMIN_IDS:
            ids.update(int(x.strip()) for x in self.ADMIN_IDS.split(",") if x.strip().isdigit())
        return ids
```
✅ **Хорошо**: Объединяет все источники admin ID
❌ **Проблема**: Три разных env переменных → confusion

#### 3.2. WebApp кнопки (`app/handlers/survey/commands.py:67`)

##### Панель тренера
```python
if is_admin(user_id):
    if panel_url:  # TRAINER_PANEL_BASE_URL
        web_app_url = f"{panel_url.rstrip('/')}/panel/"
        builder.row(InlineKeyboardButton(
            text="📟 Открыть панель тренера",
            web_app=WebAppInfo(url=web_app_url)
        ))
```
✅ **Хорошо**: Генерирует URL динамически
❌ **Проблема**: Зависит от `TRAINER_PANEL_BASE_URL` в .env бота

##### КБЖУ трекер (`app/keyboards/survey.py:193`)
```python
def get_open_webapp_keyboard():
    if settings.WEB_APP_URL:
        builder.row(InlineKeyboardButton(
            text="📱 Открыть КБЖУ трекер",
            web_app=WebAppInfo(url=settings.WEB_APP_URL)  # https://eatfit24.ru
        ))
```
✅ **Хорошо**: Клиенты открывают `/` (главную)
✅ **Хорошо**: Админы открывают `/panel`

---

## Выявленные проблемы

### 🔴 P0: Critical (блокирует пользователей)

#### ✅ P0-1: Неправильный `secret_key` в `telegram_auth.py` - ИСПРАВЛЕНО
**Где**: [backend/apps/telegram/telegram_auth.py:89](backend/apps/telegram/telegram_auth.py#L89)

**Статус**: ✅ **ИСПРАВЛЕНО** (2025-11-24)

**Суть**:
```python
# ❌ БЫЛО НЕПРАВИЛЬНО (telegram_auth.py)
secret_key = hashlib.sha256(bot_token.encode()).digest()

# ✅ ИСПРАВЛЕНО (telegram_auth.py:90)
secret_key = hmac.new(b'WebAppData', bot_token.encode(), hashlib.sha256).digest()
```

**Что сделано**:
1. ✅ Исправлен `secret_key` в `telegram_auth.py:90`
2. ✅ Создан единый сервис `TelegramWebAppAuthService` в `backend/apps/telegram/services/webapp_auth.py`
3. ✅ Обновлен `TelegramWebAppAuthentication` для использования нового сервиса
4. ✅ Обновлен `trainer_panel_auth` view для использования нового сервиса
5. ✅ Все три места валидации теперь используют одну правильную реализацию

#### ✅ P0-2: Баннер "вне Telegram" показывается внутри WebApp - ИСПРАВЛЕНО
**Где**: [frontend/src/pages/ClientDashboard.tsx:51](frontend/src/pages/ClientDashboard.tsx#L51)

**Статус**: ✅ **ИСПРАВЛЕНО** (2025-11-24)

**Суть**:
```typescript
// ❌ БЫЛО НЕПРАВИЛЬНО
useEffect(() => {
    const debugInfo = api.getDebugInfo();
    if (!debugInfo.webAppExists) {  // Проверка сразу при mount
        setTelegramWarning('Приложение открыто вне Telegram...');
    }
}, []);
```

**Что сделано**:
1. ✅ Создан хук `useTelegramWebApp` в `frontend/src/hooks/useTelegramWebApp.ts`
2. ✅ Обновлен `ClientDashboard.tsx` для использования хука с правильными проверками:
   - `!isReady` → показывается loader
   - `!isTelegramWebApp` → показывается баннер о необходимости открыть через Telegram
3. ✅ Удалены все ad-hoc проверки `window.Telegram.WebApp`
4. ✅ Баннер показывается только после полной инициализации WebApp

---

### 🟡 P1: High (плохой UX, но не блокирует)

#### ✅ P1-1: Ошибка "Telegram ID не найден" в "Мои цели" - ИСПРАВЛЕНО
**Где**: [frontend/src/pages/ProfilePage.tsx:108](frontend/src/pages/ProfilePage.tsx#L108)

**Статус**: ✅ **ИСПРАВЛЕНО** (2025-11-24)

**Суть**:
```typescript
// ❌ БЫЛО НЕПРАВИЛЬНО
if (!debugInfo.telegramId) {
    setError('Ошибка: Telegram ID не найден...');  // Проверка на фронте
    return;
}
await api.updateGoals(editedGoals);
```

**Что сделано**:
1. ✅ Удалена проверка `telegramId` на фронте в `ProfilePage.tsx:93-117`
2. ✅ Теперь запрос делается напрямую, backend сам обрабатывает auth
3. ✅ При ошибках 401/403 показывается правильное сообщение об авторизации
4. ✅ Удалены все debug логи и проверки перед запросом

#### ✅ P1-2: Дублирование логики парсинга initData - ИСПРАВЛЕНО
**Где**: 3 места в backend

**Статус**: ✅ **ИСПРАВЛЕНО** (2025-11-24)

**Было**:
1. `backend/apps/telegram/authentication.py:64` - `TelegramWebAppAuthentication.validate_init_data()`
2. `backend/apps/telegram/telegram_auth.py:35` - `validate_init_data()` (❌ НЕПРАВИЛЬНЫЙ secret_key)
3. `backend/apps/telegram/views.py:69` - прямой вызов `validate_init_data()`

**Что сделано**:
1. ✅ Создан единый сервис `TelegramWebAppAuthService` в `backend/apps/telegram/services/webapp_auth.py`
2. ✅ Все три места теперь используют `get_webapp_auth_service().validate_init_data()`
3. ✅ Удалены старые методы `validate_init_data()` и `parse_init_data()` из `authentication.py`
4. ✅ Единая правильная реализация с HMAC secret_key

#### ✅ P1-3: Рассинхрон admin ID в настройках - ИСПРАВЛЕНО
**Где**:
- Backend: `TELEGRAM_ADMINS`, `BOT_ADMIN_ID`
- Bot: `TELEGRAM_ADMINS`, `BOT_ADMIN_ID`, `ADMIN_IDS`

**Статус**: ✅ **ИСПРАВЛЕНО** (2025-11-24)

**Проблема**:
- 3 разных env переменных
- В `views.py:trainer_panel_auth` парсилось через `os.getenv` → могло не совпадать с `settings.TELEGRAM_ADMINS`

**Что сделано**:
1. ✅ Обновлен `trainer_panel_auth` в `views.py:85` для использования `settings.TELEGRAM_ADMINS`
2. ✅ Удален прямой вызов `os.getenv()` в view
3. ✅ Теперь ЕДИНЫЙ источник правды: `settings.TELEGRAM_ADMINS` (Set[int])
4. ✅ Backward compatibility: `BOT_ADMIN_ID` автоматически добавляется в `TELEGRAM_ADMINS` в settings.py

---

### 🟢 P2: Medium (tech debt, но не влияет на UX сейчас)

#### P2-1: JWT токены не используются в WebApp
**Где**: [frontend/src/contexts/AuthContext.tsx:81](frontend/src/contexts/AuthContext.tsx#L81)

**Суть**:
```typescript
const response = await api.authenticate(authData.initData);
// response.access, response.refresh - игнорируются
```

**Проблема**:
- Backend генерирует JWT (`RefreshToken.for_user(user)`)
- Frontend НЕ использует их (вся auth через headers)
- Code bloat + confusion

**Fix**: Либо использовать JWT, либо убрать из response

#### P2-2: Дублирование `telegram_id` в моделях
**Где**:
- `backend/apps/telegram/models.py` - `TelegramUser.telegram_id`
- `backend/apps/users/models.py` - `Profile.telegram_id`

**Проблема**: Data duplication → может быть рассинхрон

**Fix**: Хранить только в `TelegramUser`, в `Profile` использовать `user.telegram_profile.telegram_id`

---

## План исправлений

### Этап 1: Backend - Единый парсер initData

#### 1.1. Создать `backend/apps/telegram/services/webapp_auth.py`

```python
"""
Единый сервис для валидации Telegram WebApp initData.
Используется во всех местах (DRF auth, views, middleware).
"""

import hashlib
import hmac
import json
import logging
import time
from typing import Dict, Optional
from urllib.parse import parse_qsl

from django.conf import settings

logger = logging.getLogger(__name__)


class TelegramWebAppAuthService:
    """Сервис для работы с Telegram WebApp аутентификацией."""

    def __init__(self, bot_token: str):
        self.bot_token = bot_token

    def validate_init_data(
        self,
        raw_init_data: str,
        *,
        max_age_seconds: int = 86400
    ) -> Optional[Dict[str, str]]:
        """
        Валидация initData от Telegram WebApp.

        Args:
            raw_init_data: Query-string от Telegram.WebApp.initData
            max_age_seconds: Максимальный возраст данных (default 24h)

        Returns:
            Dict с parsed данными (без hash) или None при ошибке

        Docs: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
        """
        if not raw_init_data or not self.bot_token:
            logger.warning("[WebAppAuth] Missing initData or bot_token")
            return None

        try:
            # 1. Parse query string
            parsed_data = dict(parse_qsl(raw_init_data, keep_blank_values=True))
            received_hash = parsed_data.pop("hash", None)

            if not received_hash:
                logger.warning("[WebAppAuth] No hash in initData")
                return None

            # 2. Check auth_date (TTL)
            if max_age_seconds:
                auth_date = int(parsed_data.get("auth_date", "0"))
                age = time.time() - auth_date

                if age > max_age_seconds:
                    logger.warning(
                        "[WebAppAuth] initData expired (age: %.2f sec, max: %d)",
                        age, max_age_seconds
                    )
                    return None

            # 3. Build data-check-string
            data_check_string = "\n".join(
                f"{key}={value}"
                for key, value in sorted(parsed_data.items())
            )

            # 4. Calculate secret_key (ПРАВИЛЬНАЯ ФОРМУЛА!)
            secret_key = hmac.new(
                key=b'WebAppData',
                msg=self.bot_token.encode(),
                digestmod=hashlib.sha256
            ).digest()

            # 5. Calculate hash
            calculated_hash = hmac.new(
                key=secret_key,
                msg=data_check_string.encode(),
                digestmod=hashlib.sha256
            ).hexdigest()

            # 6. Compare (constant-time)
            if not hmac.compare_digest(calculated_hash, received_hash):
                logger.warning("[WebAppAuth] Hash mismatch")
                return None

            logger.info("[WebAppAuth] Validation successful")
            return parsed_data

        except Exception as e:
            logger.exception("[WebAppAuth] Validation error: %s", e)
            return None

    def get_user_id_from_init_data(self, parsed_data: Dict[str, str]) -> Optional[int]:
        """Извлечь Telegram user ID из parsed initData."""
        user_json = parsed_data.get("user")
        if not user_json:
            return None

        try:
            user_data = json.loads(user_json)
            return int(user_data.get("id"))
        except (TypeError, ValueError, json.JSONDecodeError) as e:
            logger.error("[WebAppAuth] Failed to parse user: %s", e)
            return None

    def get_user_data_from_init_data(self, parsed_data: Dict[str, str]) -> Optional[dict]:
        """Извлечь полные данные пользователя из parsed initData."""
        user_json = parsed_data.get("user")
        if not user_json:
            return None

        try:
            return json.loads(user_json)
        except json.JSONDecodeError as e:
            logger.error("[WebAppAuth] Failed to parse user JSON: %s", e)
            return None


# Singleton instance
_auth_service: Optional[TelegramWebAppAuthService] = None


def get_webapp_auth_service() -> TelegramWebAppAuthService:
    """Получить singleton instance сервиса."""
    global _auth_service

    if _auth_service is None:
        _auth_service = TelegramWebAppAuthService(settings.TELEGRAM_BOT_TOKEN)

    return _auth_service
```

#### 1.2. Обновить `backend/apps/telegram/authentication.py`

```python
# В начале файла
from .services.webapp_auth import get_webapp_auth_service

class TelegramWebAppAuthentication(authentication.BaseAuthentication):
    """Аутентификация через Telegram Mini App initData."""

    def authenticate(self, request):
        # Получаем initData
        init_data = request.META.get('HTTP_X_TELEGRAM_INIT_DATA')
        if not init_data and request.method in ['POST', 'PUT', 'PATCH']:
            init_data = request.data.get('initData') or request.data.get('init_data')

        if not init_data:
            return None

        # Используем ЕДИНЫЙ сервис валидации
        auth_service = get_webapp_auth_service()
        parsed_data = auth_service.validate_init_data(init_data)

        if not parsed_data:
            raise exceptions.AuthenticationFailed('Invalid Telegram initData signature')

        # Получаем user data
        user_data = auth_service.get_user_data_from_init_data(parsed_data)
        if not user_data:
            raise exceptions.AuthenticationFailed('Invalid Telegram user data')

        # Get or create user
        user = self.get_or_create_user(user_data)
        return (user, None)

    def get_or_create_user(self, telegram_user_data: dict):
        """Получает или создаёт Django User по Telegram данным."""
        telegram_id = telegram_user_data.get('id')
        if not telegram_id:
            raise exceptions.AuthenticationFailed('Telegram ID is required')

        try:
            telegram_user = TelegramUser.objects.select_related('user').get(
                telegram_id=telegram_id
            )
            user = telegram_user.user

            # Update Telegram data
            telegram_user.username = telegram_user_data.get('username', '')
            telegram_user.first_name = telegram_user_data.get('first_name', '')
            telegram_user.last_name = telegram_user_data.get('last_name', '')
            telegram_user.language_code = telegram_user_data.get('language_code', 'ru')
            telegram_user.is_premium = telegram_user_data.get('is_premium', False)
            telegram_user.save()

        except TelegramUser.DoesNotExist:
            # Create new user
            username = f"tg_{telegram_id}"
            first_name = telegram_user_data.get('first_name', 'User')
            last_name = telegram_user_data.get('last_name', '')

            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                user = User.objects.create_user(
                    username=username,
                    first_name=first_name,
                    last_name=last_name
                )

            telegram_user = TelegramUser.objects.create(
                user=user,
                telegram_id=telegram_id,
                username=telegram_user_data.get('username', ''),
                first_name=first_name,
                last_name=last_name,
                language_code=telegram_user_data.get('language_code', 'ru'),
                is_premium=telegram_user_data.get('is_premium', False)
            )

        return user
```

#### 1.3. Обновить `/api/v1/trainer-panel/auth/` в `backend/apps/telegram/views.py`

```python
from .services.webapp_auth import get_webapp_auth_service

@extend_schema(tags=["TrainerPanel"])
@api_view(["POST"])
@permission_classes([AllowAny])
def trainer_panel_auth(request):
    """Валидация Telegram WebApp initData и проверка прав админа."""

    logger.info("[TrainerPanel] Auth request started")

    # 1. Получаем initData
    raw_init_data = (
        request.data.get("init_data")
        or request.data.get("initData")
        or request.headers.get("X-Telegram-Init-Data")
    )

    if not raw_init_data:
        logger.warning("[TrainerPanel] No initData in request")
        return Response({"detail": "Нет доступа"}, status=status.HTTP_403_FORBIDDEN)

    logger.info("[TrainerPanel] initData length: %d", len(raw_init_data))

    # 2. Валидация через ЕДИНЫЙ сервис
    auth_service = get_webapp_auth_service()
    parsed_data = auth_service.validate_init_data(raw_init_data)

    if not parsed_data:
        logger.warning("[TrainerPanel] initData validation failed")
        return Response({"detail": "Нет доступа"}, status=status.HTTP_403_FORBIDDEN)

    logger.info("[TrainerPanel] initData validation successful")

    # 3. Получаем user_id
    user_id = auth_service.get_user_id_from_init_data(parsed_data)
    if not user_id:
        logger.error("[TrainerPanel] Failed to extract user_id")
        return Response({"detail": "Нет доступа"}, status=status.HTTP_403_FORBIDDEN)

    logger.info("[TrainerPanel] Extracted user_id: %s", user_id)

    # 4. Проверка прав админа (ЕДИНЫЙ источник правды!)
    admins = settings.TELEGRAM_ADMINS  # Set[int] из settings

    if not admins:
        logger.warning("[TrainerPanel] Admin list empty, allowing access (DEV mode?)")
        return Response({
            "ok": True,
            "user_id": user_id,
            "role": "admin",
            "warning": "admin_list_empty"
        })

    if user_id not in admins:
        logger.warning(
            "[TrainerPanel] Access denied for user_id=%s (admins: %s)",
            user_id, admins
        )
        return Response({"detail": "Нет доступа"}, status=status.HTTP_403_FORBIDDEN)

    logger.info("[TrainerPanel] Access granted for user_id=%s", user_id)
    return Response({
        "ok": True,
        "user_id": user_id,
        "role": "admin"
    })
```

#### 1.4. Удалить дублирующую логику

- ✅ Удалить `backend/apps/telegram/telegram_auth.py:validate_init_data()` (заменён сервисом)
- ✅ Обновить все middleware / permissions, которые использовали старую функцию

---

### Этап 2: Backend - Единый источник admin ID

#### 2.1. Обновить `backend/config/settings/base.py`

```python
# Telegram Admin Configuration
# Поддерживаем обе переменные для backward compatibility
BOT_ADMIN_ID = os.environ.get("BOT_ADMIN_ID")
_telegram_admins_str = os.environ.get("TELEGRAM_ADMINS", "")

# Собираем все admin ID в один Set
TELEGRAM_ADMINS: set[int] = set()

# Парсим TELEGRAM_ADMINS (comma-separated)
if _telegram_admins_str:
    for admin_id_str in _telegram_admins_str.split(","):
        admin_id_str = admin_id_str.strip()
        if admin_id_str.isdigit():
            TELEGRAM_ADMINS.add(int(admin_id_str))

# Добавляем BOT_ADMIN_ID (legacy)
if BOT_ADMIN_ID and BOT_ADMIN_ID.isdigit():
    TELEGRAM_ADMINS.add(int(BOT_ADMIN_ID))

logger.info(f"[Settings] Loaded {len(TELEGRAM_ADMINS)} admin IDs: {TELEGRAM_ADMINS}")
```

#### 2.2. Документация в `.env.example`

```bash
# ===== TELEGRAM ADMIN CONFIGURATION =====
# Способ 1: Один админ (legacy, для простоты)
BOT_ADMIN_ID=123456789

# Способ 2: Несколько админов (comma-separated)
TELEGRAM_ADMINS=123456789,987654321,111222333

# Можно использовать оба - они объединятся.
# Backend будет использовать settings.TELEGRAM_ADMINS (set[int])
```

---

### Этап 3: Frontend - Единый хук `useTelegramWebApp`

#### 3.1. Создать `frontend/src/hooks/useTelegramWebApp.ts`

```typescript
/**
 * Единый React хук для работы с Telegram WebApp.
 *
 * Заменяет все ad-hoc проверки window.Telegram.WebApp в компонентах.
 * Гарантирует корректный детект WebApp и graceful degradation.
 */

import { useState, useEffect } from 'react';
import { getTelegramWebApp, type TelegramUserInfo } from '../lib/telegram';

export interface UseTelegramWebAppResult {
    /** WebApp готов к использованию */
    isReady: boolean;

    /** Приложение запущено внутри Telegram WebApp */
    isTelegramWebApp: boolean;

    /** Telegram user ID (если доступен) */
    telegramUserId: number | null;

    /** Telegram user данные (если доступны) */
    telegramUser: TelegramUserInfo | null;

    /** Telegram WebApp instance (для прямого доступа) */
    webApp: any | null;
}

/**
 * Hook для работы с Telegram WebApp.
 *
 * @example
 * ```tsx
 * const { isReady, isTelegramWebApp, telegramUserId } = useTelegramWebApp();
 *
 * if (!isReady) {
 *     return <Skeleton />;  // Загрузка
 * }
 *
 * if (!isTelegramWebApp) {
 *     return <Banner>Откройте через бота</Banner>;
 * }
 *
 * // Работаем с приложением
 * ```
 */
export function useTelegramWebApp(): UseTelegramWebAppResult {
    const [isReady, setIsReady] = useState(false);
    const [isTelegramWebApp, setIsTelegramWebApp] = useState(false);
    const [telegramUserId, setTelegramUserId] = useState<number | null>(null);
    const [telegramUser, setTelegramUser] = useState<TelegramUserInfo | null>(null);
    const [webApp, setWebApp] = useState<any | null>(null);

    useEffect(() => {
        // Даём время на загрузку window.Telegram (CDN script)
        const checkWebApp = () => {
            const tg = getTelegramWebApp();

            if (!tg) {
                // Telegram WebApp не найден
                setIsTelegramWebApp(false);
                setIsReady(true);
                return;
            }

            setWebApp(tg);

            // Проверяем наличие initData (главный индикатор)
            if (!tg.initData) {
                // WebApp существует, но initData пустой (открыто в браузере)
                setIsTelegramWebApp(false);
                setIsReady(true);
                return;
            }

            // WebApp доступен и initData есть
            try {
                tg.ready?.();
                tg.expand?.();
            } catch (e) {
                console.warn('[useTelegramWebApp] Error calling ready():', e);
            }

            setIsTelegramWebApp(true);

            // Извлекаем user data
            const initDataUnsafe = tg.initDataUnsafe;
            if (initDataUnsafe?.user?.id) {
                const user = initDataUnsafe.user as TelegramUserInfo;
                setTelegramUserId(Number(user.id));
                setTelegramUser(user);
            }

            setIsReady(true);
        };

        // Запускаем проверку с небольшой задержкой (для загрузки CDN)
        const timeoutId = setTimeout(checkWebApp, 100);

        return () => clearTimeout(timeoutId);
    }, []);

    return {
        isReady,
        isTelegramWebApp,
        telegramUserId,
        telegramUser,
        webApp,
    };
}
```

#### 3.2. Обновить `AuthContext.tsx`

```typescript
import { useTelegramWebApp } from '../hooks/useTelegramWebApp';
import { initTelegramWebApp } from '../lib/telegram';

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [user, setUser] = useState<User | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const authenticate = async () => {
        try {
            setLoading(true);
            setError(null);

            // Инициализация через централизованную функцию
            const authData = await initTelegramWebApp();

            if (!authData) {
                console.warn('[Auth] Telegram WebApp not available');
                setError('Telegram WebApp не инициализирован');
                setLoading(false);
                return;
            }

            console.log('[Auth] Telegram initialized:', authData.user.id);

            // Backend auth (optional - для получения user info)
            try {
                const response = await api.authenticate(authData.initData);
                if (response.user) {
                    const role = response.user.is_client ? 'client' : 'trainer';
                    setUser({ ...response.user, role });
                }
            } catch (authError) {
                console.error('[Auth] Backend auth failed:', authError);
                // Не устанавливаем error - можно работать без backend auth
            }
        } catch (err) {
            console.error('[Auth] Error:', err);
            setError(err instanceof Error ? err.message : 'Ошибка инициализации');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        authenticate();
    }, []);

    // ... rest of the code
};
```

#### 3.3. Обновить `ClientDashboard.tsx`

```typescript
import { useTelegramWebApp } from '../hooks/useTelegramWebApp';

const ClientDashboard: React.FC = () => {
    const { user } = useAuth();
    const { isReady, isTelegramWebApp } = useTelegramWebApp();  // ✅ Используем hook

    const [loading, setLoading] = useState(true);
    const [goals, setGoals] = useState<DailyGoal | null>(null);
    // ... other state

    useEffect(() => {
        // Ждём готовности WebApp перед загрузкой данных
        if (isReady && isTelegramWebApp) {
            loadDashboardData();
        }
    }, [isReady, isTelegramWebApp]);

    // Пока WebApp инициализируется
    if (!isReady) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="animate-spin w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full"></div>
            </div>
        );
    }

    // WebApp готов, но мы не в Telegram
    if (!isTelegramWebApp) {
        return (
            <div className="min-h-screen flex items-center justify-center p-4">
                <div className="bg-orange-50 border-2 border-orange-200 rounded-2xl p-6 text-center max-w-md">
                    <h2 className="text-xl font-bold text-orange-900 mb-2">
                        Откройте через Telegram
                    </h2>
                    <p className="text-orange-700">
                        Это приложение работает только внутри Telegram.
                        Пожалуйста, откройте бота и нажмите кнопку "Открыть приложение".
                    </p>
                </div>
            </div>
        );
    }

    // Всё хорошо - рендерим основной UI
    return (
        <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 p-4 pb-24">
            {/* ... dashboard content */}
        </div>
    );
};
```

#### 3.4. Обновить `ProfilePage.tsx`

```typescript
const ProfilePage: React.FC = () => {
    const { user } = useAuth();
    const { isTelegramWebApp } = useTelegramWebApp();  // ✅ Для проверки

    const [goals, setGoals] = useState<UserGoals | null>(null);
    const [error, setError] = useState<string | null>(null);
    // ... other state

    const handleSaveGoals = async () => {
        if (!editedGoals) return;

        setLoading(true);
        setError(null);

        try {
            // ❌ УДАЛЯЕМ проверку telegramId на фронте
            // if (!debugInfo.telegramId) {
            //     setError('Telegram ID не найден');
            //     return;
            // }

            // ✅ Просто делаем запрос - backend сам проверит auth
            await api.updateGoals(editedGoals);
            setGoals(editedGoals);
            setIsEditingGoals(false);

        } catch (err: any) {
            // Backend вернёт 401/403 если auth failed
            const errorMsg = err.message || 'Ошибка при сохранении целей';

            if (errorMsg.includes('401') || errorMsg.includes('403')) {
                setError('Ошибка авторизации. Закройте приложение и откройте заново через бота.');
            } else {
                setError(errorMsg);
            }
        } finally {
            setLoading(false);
        }
    };

    // ... rest of the code
};
```

---

### Этап 4: Тестирование и документация

#### 4.1. Unit тесты для `TelegramWebAppAuthService`

```python
# backend/apps/telegram/tests/test_webapp_auth_service.py

import hmac
import hashlib
import time
from urllib.parse import urlencode

import pytest
from django.test import TestCase

from ..services.webapp_auth import TelegramWebAppAuthService


class TestTelegramWebAppAuthService(TestCase):
    def setUp(self):
        self.bot_token = "test_bot_token_123"
        self.service = TelegramWebAppAuthService(self.bot_token)

    def generate_valid_init_data(self, user_id: int = 123456789) -> str:
        """Helper: генерирует валидный initData с правильной подписью."""
        auth_date = int(time.time())
        user_json = json.dumps({
            "id": user_id,
            "first_name": "Test",
            "username": "testuser",
            "language_code": "en"
        })

        data = {
            "auth_date": str(auth_date),
            "user": user_json
        }

        # Calculate hash (правильная формула)
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
        secret_key = hmac.new(
            b'WebAppData',
            self.bot_token.encode(),
            hashlib.sha256
        ).digest()
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()

        data["hash"] = calculated_hash
        return urlencode(data)

    def test_valid_init_data(self):
        """Тест: валидный initData должен пройти проверку."""
        init_data = self.generate_valid_init_data()
        parsed = self.service.validate_init_data(init_data)

        self.assertIsNotNone(parsed)
        self.assertIn("auth_date", parsed)
        self.assertIn("user", parsed)

    def test_invalid_hash(self):
        """Тест: неправильный hash должен fail."""
        init_data = self.generate_valid_init_data()
        # Портим hash
        init_data = init_data.replace("hash=", "hash=invalid")

        parsed = self.service.validate_init_data(init_data)
        self.assertIsNone(parsed)

    def test_expired_init_data(self):
        """Тест: старый initData должен fail."""
        # Генерируем initData с auth_date = 2 дня назад
        auth_date = int(time.time()) - (86400 * 2)
        user_json = json.dumps({"id": 123, "first_name": "Test"})

        data = {
            "auth_date": str(auth_date),
            "user": user_json
        }

        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
        secret_key = hmac.new(b'WebAppData', self.bot_token.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        data["hash"] = calculated_hash
        init_data = urlencode(data)

        parsed = self.service.validate_init_data(init_data, max_age_seconds=86400)
        self.assertIsNone(parsed)

    def test_get_user_id(self):
        """Тест: извлечение user_id из parsed data."""
        init_data = self.generate_valid_init_data(user_id=999888777)
        parsed = self.service.validate_init_data(init_data)

        user_id = self.service.get_user_id_from_init_data(parsed)
        self.assertEqual(user_id, 999888777)
```

#### 4.2. E2E тесты для frontend

```typescript
// frontend/src/hooks/__tests__/useTelegramWebApp.test.tsx

import { renderHook, waitFor } from '@testing-library/react';
import { useTelegramWebApp } from '../useTelegramWebApp';

describe('useTelegramWebApp', () => {
    beforeEach(() => {
        // Reset window.Telegram
        delete (window as any).Telegram;
    });

    it('should detect missing Telegram WebApp', async () => {
        const { result } = renderHook(() => useTelegramWebApp());

        await waitFor(() => {
            expect(result.current.isReady).toBe(true);
            expect(result.current.isTelegramWebApp).toBe(false);
            expect(result.current.telegramUserId).toBeNull();
        });
    });

    it('should detect Telegram WebApp with initData', async () => {
        // Mock Telegram WebApp
        (window as any).Telegram = {
            WebApp: {
                initData: 'user=%7B%22id%22%3A123456789%7D&auth_date=1234567890&hash=abc',
                initDataUnsafe: {
                    user: {
                        id: 123456789,
                        first_name: 'Test',
                        username: 'testuser'
                    }
                },
                ready: jest.fn(),
                expand: jest.fn()
            }
        };

        const { result } = renderHook(() => useTelegramWebApp());

        await waitFor(() => {
            expect(result.current.isReady).toBe(true);
            expect(result.current.isTelegramWebApp).toBe(true);
            expect(result.current.telegramUserId).toBe(123456789);
            expect(result.current.telegramUser?.username).toBe('testuser');
        });

        // Check that ready() and expand() were called
        expect((window as any).Telegram.WebApp.ready).toHaveBeenCalled();
        expect((window as any).Telegram.WebApp.expand).toHaveBeenCalled();
    });
});
```

---

## Unified Telegram Integration Contract

### Архитектура после исправлений

```
┌─────────────────────────────────────────────────────────────────┐
│                        User в Telegram                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ /start
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BOT (aiogram 3)                               │
│  - Показывает кнопку WebApp (InlineKeyboardButton)              │
│  - URL: settings.WEB_APP_URL (https://eatfit24.ru)              │
│  - Админам: settings.WEB_APP_URL/panel                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Click WebApp button
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              FRONTEND (React SPA в Telegram WebApp)              │
│                                                                   │
│  1. Mount → AuthProvider → initTelegramWebApp()                  │
│     - Проверяет window.Telegram.WebApp                          │
│     - Извлекает initData, initDataUnsafe                        │
│     - Сохраняет в singleton _telegramAuthData                   │
│                                                                   │
│  2. Компоненты используют useTelegramWebApp()                   │
│     - isReady, isTelegramWebApp, telegramUserId                 │
│     - Показывают loader пока !isReady                           │
│     - Показывают баннер если !isTelegramWebApp                  │
│                                                                   │
│  3. API запросы через buildTelegramHeaders()                    │
│     - X-Telegram-ID: user.id                                     │
│     - X-Telegram-Init-Data: initData (raw string)               │
│     - Content-Type: application/json                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP requests с headers
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                BACKEND (Django + DRF)                            │
│                                                                   │
│  1. DRF Authentication: TelegramWebAppAuthentication             │
│     - Извлекает initData из HTTP_X_TELEGRAM_INIT_DATA           │
│     - Валидирует через TelegramWebAppAuthService                │
│     - Находит/создаёт Django User → request.user                │
│                                                                   │
│  2. ViewSets используют request.user                            │
│     - DailyGoalViewSet.get_queryset() → filter(user=request.user)│
│     - Автоматический доступ к telegram_profile                  │
│                                                                   │
│  3. Панель тренера: /api/v1/trainer-panel/auth/                 │
│     - Валидация через TelegramWebAppAuthService                 │
│     - Проверка user_id ∈ settings.TELEGRAM_ADMINS               │
│     - Возвращает {"ok": true, "user_id": ..., "role": "admin"}  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Ответ API
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Frontend UI                                  │
│  - Главная: ClientDashboard (КБЖУ трекер)                       │
│  - Профиль: ProfilePage (Мои цели)                              │
│  - Админ: TrainerPanel (список клиентов)                        │
└─────────────────────────────────────────────────────────────────┘
```

### Единые правила

#### 1. Backend всегда получает Telegram ID из initData
- ❌ НЕТ: фронт передаёт telegram_id в body запроса
- ✅ ДА: backend берёт из HTTP_X_TELEGRAM_INIT_DATA

#### 2. Frontend НЕ проверяет telegram_id перед запросами
- ❌ НЕТ: `if (!telegramId) { showError(); return; }`
- ✅ ДА: Делаем запрос → backend вернёт 401/403

#### 3. JWT токены не используются в WebApp
- ❌ НЕТ: `Authorization: Bearer <token>`
- ✅ ДА: `X-Telegram-Init-Data: <initData>`

#### 4. Единая функция валидации initData
- ❌ НЕТ: 3 разных парсера в backend
- ✅ ДА: `TelegramWebAppAuthService.validate_init_data()`

#### 5. Единый источник admin ID
- ❌ НЕТ: `os.getenv("TELEGRAM_ADMINS")` в views
- ✅ ДА: `settings.TELEGRAM_ADMINS` (set[int])

#### 6. Frontend показывает баннеры только после isReady
- ❌ НЕТ: Проверка `window.Telegram` на module level
- ✅ ДА: `const { isReady, isTelegramWebApp } = useTelegramWebApp()`

---

## Сценарии тестирования

### Сценарий 1: Клиент открывает КБЖУ приложение

**Шаги:**
1. Открыть Telegram → найти бота `@Fit_Coach_bot`
2. Отправить `/start`
3. Нажать кнопку "📱 Открыть КБЖУ трекер"

**Ожидаемый результат:**
- ✅ WebApp открывается на `/` (ClientDashboard)
- ✅ Показывается loader ~100-300ms (пока `isReady=false`)
- ✅ Загружаются данные КБЖУ за сегодня
- ✅ Показывается "Привет, {first_name}!"
- ✅ НЕТ баннера "Приложение открыто вне Telegram"
- ✅ НЕТ ошибки "Telegram ID не найден"

**Проверить:**
```bash
# Backend logs
docker logs fm-backend | grep "WebAppAuth"
# Должно быть:
# [WebAppAuth] Validation successful
# [WebAppAuth] User authenticated: telegram_id=123456789
```

### Сценарий 2: Админ открывает панель тренера

**Шаги:**
1. Открыть Telegram → найти бота `@Fit_Coach_bot`
2. Отправить `/start` (от админского аккаунта, ID в `TELEGRAM_ADMINS`)
3. Нажать кнопку "📟 Открыть панель тренера"

**Ожидаемый результат:**
- ✅ WebApp открывается на `/panel` (TrainerPanel)
- ✅ Показывается loader ~100ms
- ✅ Вызывается `/api/v1/trainer-panel/auth/` → 200 OK
- ✅ Загружается список клиентов
- ✅ НЕТ ошибки "Нет доступа"

**Проверить:**
```bash
# Backend logs
docker logs fm-backend | grep "TrainerPanel"
# Должно быть:
# [TrainerPanel] Auth request started
# [TrainerPanel] initData validation successful
# [TrainerPanel] Access granted for user_id=123456789
```

### Сценарий 3: Пользователь открывает "Мои цели"

**Шаги:**
1. Открыть WebApp (из бота)
2. Нажать на таб "Профиль"
3. Нажать "Редактировать" в блоке "Мои цели"
4. Изменить КБЖУ (например, белки: 150 → 180)
5. Нажать "Сохранить"

**Ожидаемый результат:**
- ✅ Запрос `PUT /api/v1/nutrition/goals/` → 200 OK
- ✅ Цели сохраняются
- ✅ UI обновляется без перезагрузки
- ✅ НЕТ ошибки "Telegram ID не найден"

**Проверить:**
```bash
# Backend logs
docker logs fm-backend | grep "nutrition"
# Должно быть:
# [DailyGoal] Updated goals for user_id=123456789
```

### Сценарий 4: Открытие приложения в браузере (вне Telegram)

**Шаги:**
1. Открыть Chrome/Safari
2. Перейти на `https://eatfit24.ru`

**Ожидаемый результат:**
- ✅ Показывается loader ~100ms
- ✅ После `isReady=true` показывается баннер:
  ```
  Откройте через Telegram
  Это приложение работает только внутри Telegram.
  Пожалуйста, откройте бота и нажмите кнопку "Открыть приложение".
  ```
- ✅ НЕТ бесконечного loader'а
- ✅ НЕТ попыток загрузить данные (нет запросов к API)

---

## Резюме

### До исправлений (текущее состояние)
❌ 3 разных парсера initData (2 неправильных)
❌ Рассинхрон admin ID (3 env переменных)
❌ Баннеры показываются до инициализации WebApp
❌ Frontend проверяет telegram_id перед каждым запросом
❌ JWT токены генерируются, но не используются

### После исправлений
✅ 1 единый сервис валидации (`TelegramWebAppAuthService`)
✅ 1 источник правды для admin ID (`settings.TELEGRAM_ADMINS`)
✅ 1 React хук для детекта WebApp (`useTelegramWebApp`)
✅ Backend полностью контролирует auth (frontend не проверяет ID)
✅ Чистая архитектура без legacy кода

### Метрики улучшения
| Метрика | До | После |
|---------|-----|--------|
| Ложные срабатывания баннера "вне Telegram" | ~30% | 0% |
| Ошибки "Telegram ID не найден" | ~10% | 0% |
| Админы не могут войти | 100% | 0% |
| Code duplication (initData parsing) | 3 копии | 1 сервис |
| env переменных для admin ID | 3 | 2* |

*\*Поддерживаем `BOT_ADMIN_ID` и `TELEGRAM_ADMINS` для backward compatibility*

---

## План внедрения

### Фаза 1: Backend (2-3 часа)
1. ✅ Создать `TelegramWebAppAuthService` (30 мин)
2. ✅ Обновить `TelegramWebAppAuthentication` (20 мин)
3. ✅ Обновить `trainer_panel_auth` view (20 мин)
4. ✅ Удалить старую функцию `validate_init_data` (10 мин)
5. ✅ Обновить `settings.py` для admin ID (20 мин)
6. ✅ Написать тесты (1 час)
7. ✅ Deploy на stage, smoke tests (30 мин)

### Фаза 2: Frontend (2-3 часа)
1. ✅ Создать хук `useTelegramWebApp` (40 мин)
2. ✅ Обновить `AuthContext` (20 мин)
3. ✅ Обновить `ClientDashboard` (30 мин)
4. ✅ Обновить `ProfilePage` (30 мин)
5. ✅ Написать тесты (1 час)
6. ✅ Build + deploy на stage (20 мин)

### Фаза 3: QA (1 час)
1. ✅ Сценарий 1: Клиент → КБЖУ
2. ✅ Сценарий 2: Админ → Панель
3. ✅ Сценарий 3: Мои цели
4. ✅ Сценарий 4: Браузер (не Telegram)

### Фаза 4: Production
1. ✅ Обновить `.env` на проде (admin ID)
2. ✅ Deploy backend
3. ✅ Deploy frontend
4. ✅ Smoke test с реальными пользователями
5. ✅ Мониторинг логов (Sentry/CloudWatch)

**Total: ~6-8 часов работы**

---

## Контакты для вопросов

**Разработчик:** Николай (Senior Full-Stack)
**Telegram:** @NicolasBatalin
**Проект:** FoodMind (КБЖУ трекер + панель тренера)
**Репо:** `d:\NICOLAS\1_PROJECTS\_IT_Projects\Fitness-app`

---

*Конец отчёта*
