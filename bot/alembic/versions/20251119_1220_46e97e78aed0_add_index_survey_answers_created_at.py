"""add_index_survey_answers_created_at

Revision ID: 46e97e78aed0
Revises: 6aa0ade7a7c0
Create Date: 2025-11-19 12:20:38.584296

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '46e97e78aed0'
down_revision: Union[str, None] = '6aa0ade7a7c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Добавляет индекс на survey_answers.created_at для аналитики времени начала опроса."""
    op.create_index(
        'ix_survey_answers_created_at',
        'survey_answers',
        ['created_at']
    )


def downgrade() -> None:
    """Удаляет индекс survey_answers.created_at."""
    op.drop_index('ix_survey_answers_created_at', 'survey_answers')
