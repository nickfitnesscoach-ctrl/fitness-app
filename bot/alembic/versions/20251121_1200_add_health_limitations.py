"""Add health limitations field to survey answers

Revision ID: 9b6a4c21d3ef
Revises: 1d2f4b7c8e21
Create Date: 2025-11-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '9b6a4c21d3ef'
down_revision: Union[str, None] = '1d2f4b7c8e21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('survey_answers', sa.Column('health_limitations', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('survey_answers', 'health_limitations')
