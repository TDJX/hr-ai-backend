"""add dialogue_history column only

Revision ID: 9d415bf0ff2e
Revises: 53d8b753cb71
Create Date: 2025-09-03 18:04:49.726882

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9d415bf0ff2e"
down_revision: str | Sequence[str] | None = "c2d48b31ee30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Сначала создаем таблицу interview_sessions (если была удалена)
    op.create_table(
        "interview_sessions",
        sa.Column("resume_id", sa.Integer(), nullable=False),
        sa.Column("room_name", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.TEXT(),
            nullable=True,
        ),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("ai_feedback", sa.Text(), nullable=True),
        sa.Column("dialogue_history", sa.JSON(), nullable=True),
        sa.Column("ai_agent_pid", sa.Integer(), nullable=True),
        sa.Column("ai_agent_status", sa.String(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
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
    # Удаляем всю таблицу
    op.drop_table("interview_sessions")
