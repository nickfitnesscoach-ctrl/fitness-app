"""
Репозиторий для работы с базой данных.
"""

from datetime import datetime, date
from typing import Optional, Dict, Any
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, SurveyAnswer, Plan
from app.utils.logger import logger


class UserRepository:
    """Репозиторий для работы с пользователями."""

    @staticmethod
    async def get_or_create(
        session: AsyncSession,
        tg_id: int,
        username: Optional[str] = None,
        full_name: Optional[str] = None
    ) -> User:
        """
        Получить пользователя или создать нового.

        Args:
            session: Async сессия БД
            tg_id: Telegram ID пользователя
            username: Username (опционально)
            full_name: Полное имя (опционально)

        Returns:
            User object
        """
        # Попытка найти существующего пользователя
        result = await session.execute(
            select(User).where(User.tg_id == tg_id)
        )
        user = result.scalar_one_or_none()

        if user:
            # Обновить username и full_name если изменились
            if username and user.username != username:
                user.username = username
            if full_name and user.full_name != full_name:
                user.full_name = full_name
            await session.commit()
            return user

        # Создать нового пользователя
        user = User(
            tg_id=tg_id,
            username=username,
            full_name=full_name
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        logger.info(f"Created new user: tg_id={tg_id}, username={username}")
        return user


class SurveyRepository:
    """Репозиторий для работы с ответами опроса."""

    @staticmethod
    async def create_survey_answer(
        session: AsyncSession,
        user_id: int,
        data: Dict[str, Any]
    ) -> SurveyAnswer:
        """
        Создать запись с ответами опроса.

        Args:
            session: Async сессия БД
            user_id: ID пользователя
            data: Данные опроса из FSM state

        Returns:
            SurveyAnswer object
        """
        survey = SurveyAnswer(
            user_id=user_id,
            gender=data["gender"],
            age=data["age"],
            height_cm=data["height_cm"],
            weight_kg=data["weight_kg"],
            target_weight_kg=data.get("target_weight_kg"),
            activity=data["activity"],
            training_level=data.get("training_level"),
            body_goals=data.get("body_goals"),
            health_limitations=data.get("health_limitations"),
            body_now_id=data["body_now_id"],
            body_now_label=data.get("body_now_label"),
            body_now_file=data["body_now_file"],
            body_ideal_id=data["body_ideal_id"],
            body_ideal_label=data.get("body_ideal_label"),
            body_ideal_file=data["body_ideal_file"],
            tz=data["tz"],
            utc_offset_minutes=data["utc_offset_minutes"],
            completed_at=datetime.now()
        )

        session.add(survey)
        await session.commit()
        await session.refresh(survey)

        logger.info(f"Created survey answer: user_id={user_id}, survey_id={survey.id}")
        return survey


class PlanRepository:
    """Репозиторий для работы с планами."""

    @staticmethod
    async def create_plan(
        session: AsyncSession,
        user_id: int,
        survey_answer_id: Optional[int],
        ai_text: str,
        ai_model: str,
        prompt_version: str
    ) -> Plan:
        """
        Создать запись с ИИ-планом.

        Args:
            session: Async сессия БД
            user_id: ID пользователя
            survey_answer_id: ID ответа на опрос
            ai_text: Текст плана от ИИ
            ai_model: Использованная модель
            prompt_version: Версия промпта

        Returns:
            Plan object
        """
        plan = Plan(
            user_id=user_id,
            survey_answer_id=survey_answer_id,
            ai_text=ai_text,
            ai_model=ai_model,
            prompt_version=prompt_version
        )

        session.add(plan)
        await session.commit()
        await session.refresh(plan)

        logger.info(f"Created plan: user_id={user_id}, plan_id={plan.id}, model={ai_model}")
        return plan

    @staticmethod
    async def count_plans_today(session: AsyncSession, user_id: int) -> int:
        """
        Подсчитать количество планов, сгенерированных пользователем сегодня.

        Args:
            session: Async сессия БД
            user_id: ID пользователя

        Returns:
            Количество планов за сегодня
        """
        today_start = datetime.combine(date.today(), datetime.min.time())

        result = await session.execute(
            select(func.count(Plan.id))
            .where(Plan.user_id == user_id)
            .where(Plan.created_at >= today_start)
        )
        count = result.scalar_one()

        return count
