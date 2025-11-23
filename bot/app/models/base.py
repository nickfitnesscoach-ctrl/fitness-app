"""
Базовые модели SQLAlchemy для всех таблиц.
"""

from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import BigInteger, TIMESTAMP, func
from datetime import datetime


class Base(AsyncAttrs, DeclarativeBase):
    """Базовый класс для всех моделей."""
    pass


class TimestampMixin:
    """Миксин для добавления timestamp полей created_at и updated_at."""

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
