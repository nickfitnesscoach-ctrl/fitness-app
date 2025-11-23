"""
Управление сессиями базы данных.
"""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from typing import AsyncGenerator

from app.config import settings
from app.models.base import Base
from app.utils.logger import logger


# Создать async engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.DEBUG_MODE,  # Логировать SQL запросы в debug режиме
    pool_pre_ping=True,  # Проверять соединение перед использованием
    pool_size=20,  # Размер основного пула соединений
    max_overflow=30,  # Дополнительные соединения при пиковых нагрузках
    pool_recycle=3600,  # Переиспользовать соединения каждый час (против idle connections)
)

# Создать session maker
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency для получения async сессии БД.

    Yields:
        AsyncSession
    """
    async with async_session_maker() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Database session error: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Инициализация базы данных (создание таблиц)."""
    async with engine.begin() as conn:
        # В production используйте Alembic миграции вместо create_all
        # await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized (use Alembic for migrations in production)")


async def close_db():
    """Закрытие соединения с базой данных."""
    await engine.dispose()
    logger.info("Database connection closed")
