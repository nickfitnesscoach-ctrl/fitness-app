"""
Модели для опроса Personal Plan.
"""

from sqlalchemy import BigInteger, String, Integer, Numeric, Text, ForeignKey, CheckConstraint, TIMESTAMP, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, List
from datetime import datetime

from .base import Base


class SurveyAnswer(Base):
    """Ответы пользователя на опрос Personal Plan."""

    __tablename__ = "survey_answers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Ответы опроса
    gender: Mapped[str] = mapped_column(String(10), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    height_cm: Mapped[int] = mapped_column(Integer, nullable=False)
    weight_kg: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    target_weight_kg: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    activity: Mapped[str] = mapped_column(String(20), nullable=False)
    training_level: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    body_goals: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)
    health_limitations: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)

    # Типы фигуры
    body_now_id: Mapped[int] = mapped_column(Integer, nullable=False)
    body_now_label: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    body_now_file: Mapped[str] = mapped_column(Text, nullable=False)

    body_ideal_id: Mapped[int] = mapped_column(Integer, nullable=False)
    body_ideal_label: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    body_ideal_file: Mapped[str] = mapped_column(Text, nullable=False)

    # Часовой пояс
    tz: Mapped[str] = mapped_column(String(64), nullable=False, default="Europe/Moscow")
    utc_offset_minutes: Mapped[int] = mapped_column(Integer, nullable=False)

    # Метаданные
    completed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default="now()", nullable=False)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="survey_answers")
    plans: Mapped[List["Plan"]] = relationship(back_populates="survey_answer")

    __table_args__ = (
        CheckConstraint("gender IN ('male', 'female')", name="check_gender"),
        CheckConstraint("age BETWEEN 14 AND 80", name="check_age"),
        CheckConstraint("height_cm BETWEEN 120 AND 250", name="check_height"),
        CheckConstraint("weight_kg BETWEEN 30 AND 300", name="check_weight"),
        CheckConstraint(
            "target_weight_kg IS NULL OR target_weight_kg BETWEEN 30 AND 300",
            name="check_target_weight"
        ),
        CheckConstraint(
            "activity IN ('sedentary', 'light', 'moderate', 'active', 'very_active')",
            name="check_activity"
        ),
    )

    def __repr__(self) -> str:
        return f"<SurveyAnswer(id={self.id}, user_id={self.user_id}, gender={self.gender}, age={self.age})>"


class Plan(Base):
    """ИИ-генерированные планы питания и тренировок."""

    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    survey_answer_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("survey_answers.id", ondelete="SET NULL"),
        nullable=True
    )

    # Ответ ИИ
    ai_text: Mapped[str] = mapped_column(Text, nullable=False)
    ai_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Метаданные
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default="now()",
        nullable=False,
        index=True
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="plans")
    survey_answer: Mapped[Optional["SurveyAnswer"]] = relationship(back_populates="plans")

    def __repr__(self) -> str:
        return f"<Plan(id={self.id}, user_id={self.user_id}, model={self.ai_model})>"
