"""change json fields to text for proper utf8

Revision ID: a816820baadb
Revises: c9bcdd2ddeeb
Create Date: 2025-09-03 23:45:13.221735

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a816820baadb'
down_revision: Union[str, Sequence[str], None] = 'c9bcdd2ddeeb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Change JSON fields to TEXT for proper UTF-8 handling."""
    # Convert JSON fields to TEXT for proper UTF-8 storage
    op.execute("""
        ALTER TABLE resume 
        ALTER COLUMN parsed_data TYPE TEXT USING parsed_data::TEXT,
        ALTER COLUMN interview_plan TYPE TEXT USING interview_plan::TEXT
    """)
    
    op.execute("""
        ALTER TABLE interview_sessions 
        ALTER COLUMN dialogue_history TYPE TEXT USING dialogue_history::TEXT
    """)
    
    # Also fix status column
    op.alter_column('interview_sessions', 'status',
               existing_type=sa.VARCHAR(length=50),
               nullable=False,
               existing_server_default=sa.text("'created'::character varying"))


def downgrade() -> None:
    """Convert TEXT fields back to JSON."""
    # Convert TEXT fields back to JSON
    op.execute("""
        ALTER TABLE resume 
        ALTER COLUMN parsed_data TYPE JSON USING parsed_data::JSON,
        ALTER COLUMN interview_plan TYPE JSON USING interview_plan::JSON
    """)
    
    op.execute("""
        ALTER TABLE interview_sessions 
        ALTER COLUMN dialogue_history TYPE JSON USING dialogue_history::JSON
    """)
    
    op.alter_column('interview_sessions', 'status',
               existing_type=sa.VARCHAR(length=50),
               nullable=True,
               existing_server_default=sa.text("'created'::character varying"))
