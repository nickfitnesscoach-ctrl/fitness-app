"""create_survey_tables

Revision ID: 6aa0ade7a7c0
Revises: 
Create Date: 2025-11-16 18:09:34.538225

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6aa0ade7a7c0'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Создать таблицу users
    op.create_table(
        'users',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('tg_id', sa.BigInteger(), nullable=False),
        sa.Column('username', sa.String(255), nullable=True),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('tz', sa.String(64), server_default='Europe/Moscow', nullable=False),
        sa.Column('utc_offset_minutes', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tg_id')
    )
    op.create_index('ix_users_tg_id', 'users', ['tg_id'])

    # Создать таблицу survey_answers
    op.create_table(
        'survey_answers',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('gender', sa.String(10), nullable=False),
        sa.Column('age', sa.Integer(), nullable=False),
        sa.Column('height_cm', sa.Integer(), nullable=False),
        sa.Column('weight_kg', sa.Numeric(5, 2), nullable=False),
        sa.Column('target_weight_kg', sa.Numeric(5, 2), nullable=True),
        sa.Column('activity', sa.String(20), nullable=False),
        sa.Column('body_now_id', sa.Integer(), nullable=False),
        sa.Column('body_now_label', sa.Text(), nullable=True),
        sa.Column('body_now_file', sa.Text(), nullable=False),
        sa.Column('body_ideal_id', sa.Integer(), nullable=False),
        sa.Column('body_ideal_label', sa.Text(), nullable=True),
        sa.Column('body_ideal_file', sa.Text(), nullable=False),
        sa.Column('tz', sa.String(64), server_default='Europe/Moscow', nullable=False),
        sa.Column('utc_offset_minutes', sa.Integer(), nullable=False),
        sa.Column('completed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.CheckConstraint("gender IN ('male', 'female')", name='check_gender'),
        sa.CheckConstraint('age BETWEEN 14 AND 80', name='check_age'),
        sa.CheckConstraint('height_cm BETWEEN 120 AND 250', name='check_height'),
        sa.CheckConstraint('weight_kg BETWEEN 30 AND 300', name='check_weight'),
        sa.CheckConstraint('target_weight_kg IS NULL OR target_weight_kg BETWEEN 30 AND 300', name='check_target_weight'),
        sa.CheckConstraint("activity IN ('sedentary', 'light', 'moderate', 'active', 'very_active')", name='check_activity')
    )
    op.create_index('ix_survey_answers_user_id', 'survey_answers', ['user_id'])
    op.create_index('ix_survey_answers_completed_at', 'survey_answers', ['completed_at'])

    # Создать таблицу plans
    op.create_table(
        'plans',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('survey_answer_id', sa.BigInteger(), nullable=True),
        sa.Column('ai_text', sa.Text(), nullable=False),
        sa.Column('ai_model', sa.String(100), nullable=True),
        sa.Column('prompt_version', sa.String(20), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['survey_answer_id'], ['survey_answers.id'], ondelete='SET NULL')
    )
    op.create_index('ix_plans_user_id', 'plans', ['user_id'])
    op.create_index('ix_plans_created_at', 'plans', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_plans_created_at', 'plans')
    op.drop_index('ix_plans_user_id', 'plans')
    op.drop_table('plans')

    op.drop_index('ix_survey_answers_completed_at', 'survey_answers')
    op.drop_index('ix_survey_answers_user_id', 'survey_answers')
    op.drop_table('survey_answers')

    op.drop_index('ix_users_tg_id', 'users')
    op.drop_table('users')
