"""add interview_plan to resume

Revision ID: 1a2cda4df181
Revises: 4d04e6e32445
Create Date: 2025-09-02 23:38:36.541565

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1a2cda4df181'
down_revision: Union[str, Sequence[str], None] = '4d04e6e32445'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add interview_plan column to resume table
    op.add_column('resume', sa.Column('interview_plan', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Drop interview_plan column
    op.drop_column('resume', 'interview_plan')
