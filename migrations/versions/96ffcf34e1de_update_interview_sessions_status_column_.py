"""Update interview_sessions status column to use enum

Revision ID: 96ffcf34e1de
Revises: 385d03e3281c
Create Date: 2025-09-02 20:01:52.904608

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '96ffcf34e1de'
down_revision: Union[str, Sequence[str], None] = '385d03e3281c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Update status column to use interviewstatus enum
    op.execute("ALTER TABLE interview_sessions ALTER COLUMN status TYPE interviewstatus USING status::interviewstatus")


def downgrade() -> None:
    """Downgrade schema."""
    # Revert status column back to VARCHAR
    op.execute("ALTER TABLE interview_sessions ALTER COLUMN status TYPE VARCHAR(50)")
