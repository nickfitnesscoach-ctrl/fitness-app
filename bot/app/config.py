"""
Конфигурация бота - загрузка настроек из .env файла.
"""

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения из переменных окружения."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Telegram Bot
    TELEGRAM_BOT_TOKEN: str
    BOT_ADMIN_ID: int

    # Database
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "calorie_bot_db"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    FSM_STORAGE_TYPE: str = "memory"  # "redis" or "memory"

    # OpenRouter AI
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_API_KEY: str
    OPENROUTER_MODEL: str = "meta-llama/llama-3.1-70b-instruct"
    OPENROUTER_TIMEOUT: int = 30
    AI_PROMPT_VERSION: str = "v1.0"

    # OpenRouter Retry Configuration
    OPENROUTER_RETRY_ATTEMPTS: int = 3  # Количество попыток при ошибке
    OPENROUTER_RETRY_MIN_WAIT: int = 2  # Минимальная задержка между попытками (сек)
    OPENROUTER_RETRY_MAX_WAIT: int = 10  # Максимальная задержка между попытками (сек)
    OPENROUTER_RETRY_MULTIPLIER: int = 2  # Множитель для exponential backoff

    # Feature Flags
    FEATURE_PERSONAL_PLAN: str = "on"
    DEBUG_MODE: bool = False

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/bot.log"
    LOG_MAX_BYTES: int = 10485760  # 10 MB
    LOG_BACKUP_COUNT: int = 5

    # Application Settings
    DEFAULT_TIMEZONE: str = "Europe/Moscow"
    FSM_STATE_TTL: int = 30  # minutes
    IMAGE_CACHE_TTL: int = 30  # days
    RATE_LIMIT_PER_MINUTE: int = 20
    MAX_PLANS_PER_DAY: int = 3  # Максимум планов в день на пользователя
    TRAINER_USERNAME: str = "NicolasBatalin"  # Telegram username тренера (без @)
    PROJECT_URL: str = "https://github.com/your-username/ai-lead-magnet-bot"  # URL проекта для OpenRouter

    # Django API Integration
    DJANGO_API_URL: Optional[str] = None  # URL Django API (например, "http://backend:8000/api/v1" в Docker или "https://eatfit24.ru/api/v1" снаружи)

    # Django API Retry Configuration
    DJANGO_RETRY_ATTEMPTS: int = 3  # Количество попыток при ошибке
    DJANGO_RETRY_MIN_WAIT: int = 1  # Минимальная задержка между попытками (сек)
    DJANGO_RETRY_MAX_WAIT: int = 8  # Максимальная задержка между попытками (сек)
    DJANGO_RETRY_MULTIPLIER: int = 2  # Множитель для exponential backoff
    DJANGO_API_TIMEOUT: int = 30  # Timeout для запросов к Django API (сек)

    # Telegram Mini App
    WEB_APP_URL: Optional[str] = None  # URL для Telegram Mini App (e.g., "https://your-domain.com" or ngrok URL)

    # Environment
    ENVIRONMENT: str = "development"

    @property
    def database_url(self) -> str:
        """Формирует DATABASE_URL для async SQLAlchemy."""
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def is_personal_plan_enabled(self) -> bool:
        """Проверяет, включена ли функция Personal Plan."""
        return self.FEATURE_PERSONAL_PLAN.lower() == "on"

    @property
    def is_production(self) -> bool:
        """Проверяет, запущен ли бот в production окружении."""
        return self.ENVIRONMENT.lower() == "production"


# Глобальный экземпляр настроек
settings = Settings()
