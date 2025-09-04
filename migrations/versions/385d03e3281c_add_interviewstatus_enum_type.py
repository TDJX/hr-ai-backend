"""Add InterviewStatus enum type

Revision ID: 385d03e3281c
Revises: 4723b138a3bb
Create Date: 2025-09-02 20:00:00.689080

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "385d03e3281c"
down_revision: str | Sequence[str] | None = "4723b138a3bb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create InterviewStatus enum type
    interview_status_enum = sa.Enum(
        "created", "active", "completed", "failed", name="interviewstatus"
    )
    interview_status_enum.create(op.get_bind())


def downgrade() -> None:
    """Downgrade schema."""
    # Drop InterviewStatus enum type
    interview_status_enum = sa.Enum(
        "created", "active", "completed", "failed", name="interviewstatus"
    )
    interview_status_enum.drop(op.get_bind())
