"""Add training level and body goals fields

Revision ID: 1d2f4b7c8e21
Revises: 46e97e78aed0
Create Date: 2025-11-20 00:01:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '1d2f4b7c8e21'
down_revision: Union[str, None] = '46e97e78aed0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'survey_answers',
        sa.Column('training_level', sa.String(length=32), nullable=True)
    )
    op.add_column(
        'survey_answers',
        sa.Column('body_goals', sa.JSON(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('survey_answers', 'body_goals')
    op.drop_column('survey_answers', 'training_level')
