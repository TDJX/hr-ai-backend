"""add ai agent process tracking

Revision ID: de11b016b35a
Revises: 1a2cda4df181
Create Date: 2025-09-03 00:02:24.263636

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "de11b016b35a"
down_revision: str | Sequence[str] | None = "1a2cda4df181"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add AI agent process tracking columns
    op.add_column(
        "interview_sessions", sa.Column("ai_agent_pid", sa.Integer(), nullable=True)
    )
    op.add_column(
        "interview_sessions",
        sa.Column(
            "ai_agent_status", sa.String(), server_default="not_started", nullable=False
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop AI agent process tracking columns
    op.drop_column("interview_sessions", "ai_agent_status")
    op.drop_column("interview_sessions", "ai_agent_pid")
