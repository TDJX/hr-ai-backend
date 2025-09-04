"""revert json fields back to json type

Revision ID: 772538626a9e
Revises: a816820baadb
Create Date: 2025-09-04 00:02:15.230498

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '772538626a9e'
down_revision: Union[str, Sequence[str], None] = 'a816820baadb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Convert TEXT fields back to JSON for proper dict handling
    op.execute("""
        ALTER TABLE resume 
        ALTER COLUMN parsed_data TYPE JSON USING parsed_data::JSON,
        ALTER COLUMN interview_plan TYPE JSON USING interview_plan::JSON
    """)
    
    op.execute("""
        ALTER TABLE interview_sessions 
        ALTER COLUMN dialogue_history TYPE JSON USING dialogue_history::JSON
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # Convert JSON fields back to TEXT
    op.execute("""
        ALTER TABLE resume 
        ALTER COLUMN parsed_data TYPE TEXT USING parsed_data::TEXT,
        ALTER COLUMN interview_plan TYPE TEXT USING interview_plan::TEXT
    """)
    
    op.execute("""
        ALTER TABLE interview_sessions 
        ALTER COLUMN dialogue_history TYPE TEXT USING dialogue_history::TEXT
    """)
