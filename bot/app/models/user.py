"""
Модель пользователя.
"""

from sqlalchemy import BigInteger, String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, List

from .base import Base, TimestampMixin


class User(Base, TimestampMixin):
    """Модель пользователя Telegram."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Часовой пояс
    tz: Mapped[str] = mapped_column(String(64), default="Europe/Moscow", nullable=False)
    utc_offset_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    survey_answers: Mapped[List["SurveyAnswer"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    plans: Mapped[List["Plan"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, tg_id={self.tg_id}, username={self.username})>"
