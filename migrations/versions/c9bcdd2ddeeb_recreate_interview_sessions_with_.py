"""recreate interview_sessions with varchar status

Revision ID: c9bcdd2ddeeb
Revises: 9d415bf0ff2e
Create Date: 2025-09-03 18:07:59.433986

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9bcdd2ddeeb"
down_revision: str | Sequence[str] | None = "9d415bf0ff2e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Создаем таблицу interview_sessions заново
    op.execute("DROP TABLE IF EXISTS interview_sessions CASCADE")

    op.create_table(
        "interview_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("resume_id", sa.Integer(), nullable=False),
        sa.Column("room_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(50), nullable=True, server_default="created"),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("ai_feedback", sa.Text(), nullable=True),
        sa.Column("dialogue_history", sa.JSON(), nullable=True),
        sa.Column("ai_agent_pid", sa.Integer(), nullable=True),
        sa.Column(
            "ai_agent_status",
            sa.String(50),
            nullable=False,
            server_default="not_started",
        ),
        sa.Column(
            "started_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["resume_id"],
            ["resume.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("room_name"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("interview_sessions")
