"""Update InterviewSession model to use proper enum

Revision ID: 4d04e6e32445
Revises: 96ffcf34e1de
Create Date: 2025-09-02 20:10:52.321402

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "4d04e6e32445"
down_revision: str | Sequence[str] | None = "96ffcf34e1de"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Recreate interview_sessions table with proper enum (enum already exists)
    op.drop_index(op.f("ix_interview_sessions_id"), table_name="interview_sessions")
    op.drop_table("interview_sessions")

    # Create table with existing enum type
    op.create_table(
        "interview_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("resume_id", sa.Integer(), nullable=False),
        sa.Column("room_name", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "created",
                "active",
                "completed",
                "failed",
                name="interviewstatus",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("ai_feedback", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["resume_id"],
            ["resume.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("room_name"),
    )
    op.create_index(
        op.f("ix_interview_sessions_id"), "interview_sessions", ["id"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_interview_sessions_id"), table_name="interview_sessions")
    op.drop_table("interview_sessions")

    # Recreate old table structure
    op.create_table(
        "interview_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("resume_id", sa.Integer(), nullable=False),
        sa.Column("room_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("ai_feedback", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["resume_id"],
            ["resume.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("room_name"),
    )
    op.create_index(
        op.f("ix_interview_sessions_id"), "interview_sessions", ["id"], unique=False
    )
