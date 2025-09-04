"""add interview reports table with scoring fields

Revision ID: 9c60c15f7846
Revises: 772538626a9e
Create Date: 2025-09-04 12:16:56.495018

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9c60c15f7846"
down_revision: str | Sequence[str] | None = "772538626a9e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create interview reports table with scoring fields."""

    # Create enum type for recommendation
    op.execute(
        "CREATE TYPE recommendationtype AS ENUM ('STRONGLY_RECOMMEND', 'RECOMMEND', 'CONSIDER', 'REJECT')"
    )

    # Create interview_reports table
    op.execute("""
    CREATE TABLE interview_reports (
        id SERIAL PRIMARY KEY,
        interview_session_id INTEGER NOT NULL UNIQUE,
        
        -- Core scoring criteria (0-100)
        technical_skills_score INTEGER NOT NULL CHECK (technical_skills_score >= 0 AND technical_skills_score <= 100),
        technical_skills_justification VARCHAR(1000),
        technical_skills_concerns VARCHAR(500),
        
        experience_relevance_score INTEGER NOT NULL CHECK (experience_relevance_score >= 0 AND experience_relevance_score <= 100),
        experience_relevance_justification VARCHAR(1000),
        experience_relevance_concerns VARCHAR(500),
        
        communication_score INTEGER NOT NULL CHECK (communication_score >= 0 AND communication_score <= 100),
        communication_justification VARCHAR(1000),
        communication_concerns VARCHAR(500),
        
        problem_solving_score INTEGER NOT NULL CHECK (problem_solving_score >= 0 AND problem_solving_score <= 100),
        problem_solving_justification VARCHAR(1000),
        problem_solving_concerns VARCHAR(500),
        
        cultural_fit_score INTEGER NOT NULL CHECK (cultural_fit_score >= 0 AND cultural_fit_score <= 100),
        cultural_fit_justification VARCHAR(1000),
        cultural_fit_concerns VARCHAR(500),
        
        -- Aggregated fields
        overall_score INTEGER NOT NULL CHECK (overall_score >= 0 AND overall_score <= 100),
        recommendation recommendationtype NOT NULL,
        
        -- Analysis arrays
        strengths JSON,
        weaknesses JSON,
        red_flags JSON,
        
        -- Interview metrics
        questions_quality_score FLOAT CHECK (questions_quality_score >= 0 AND questions_quality_score <= 10),
        interview_duration_minutes INTEGER CHECK (interview_duration_minutes >= 0),
        response_count INTEGER CHECK (response_count >= 0),
        dialogue_messages_count INTEGER CHECK (dialogue_messages_count >= 0),
        
        -- Additional info
        next_steps VARCHAR(1000),
        interviewer_notes TEXT,
        questions_analysis JSON,
        
        -- Analysis metadata
        analysis_method VARCHAR(50) DEFAULT 'openai_gpt4',
        llm_model_used VARCHAR(100),
        analysis_duration_seconds INTEGER CHECK (analysis_duration_seconds >= 0),
        
        -- Timestamps
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
        
        -- Foreign key
        FOREIGN KEY (interview_session_id) REFERENCES interview_sessions(id)
    )
    """)

    # Create useful indexes
    op.execute(
        "CREATE INDEX idx_interview_reports_overall_score ON interview_reports (overall_score DESC)"
    )
    op.execute(
        "CREATE INDEX idx_interview_reports_recommendation ON interview_reports (recommendation)"
    )
    op.execute(
        "CREATE INDEX idx_interview_reports_technical_skills ON interview_reports (technical_skills_score DESC)"
    )
    op.execute(
        "CREATE INDEX idx_interview_reports_communication ON interview_reports (communication_score DESC)"
    )
    op.execute(
        "CREATE INDEX idx_interview_reports_session_id ON interview_reports (interview_session_id)"
    )


def downgrade() -> None:
    """Drop interview reports table."""
    op.execute("DROP TABLE IF EXISTS interview_reports")
    op.execute("DROP TYPE IF EXISTS recommendationtype")
