from datetime import datetime
from enum import Enum
from typing import Any, Optional

from sqlalchemy import JSON
from sqlmodel import Column, Field, Relationship, SQLModel


class InterviewStatus(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"

    def __str__(self):
        return self.value


class InterviewSessionBase(SQLModel):
    resume_id: int = Field(foreign_key="resume.id")
    room_name: str = Field(max_length=255, unique=True)
    status: str = Field(default="created", max_length=50)
    transcript: str | None = None
    ai_feedback: str | None = None
    dialogue_history: list[dict[str, Any]] | None = Field(
        default=None, sa_column=Column(JSON)
    )
    # Добавляем отслеживание AI процесса
    ai_agent_pid: int | None = None
    ai_agent_status: str = Field(
        default="not_started"
    )  # not_started, running, stopped, failed


class InterviewSession(InterviewSessionBase, table=True):
    __tablename__ = "interview_sessions"

    id: int | None = Field(default=None, primary_key=True)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None

    # Связь с отчетом (один к одному)
    report: Optional["InterviewReport"] = Relationship(
        back_populates="interview_session"
    )


class InterviewSessionCreate(SQLModel):
    resume_id: int
    room_name: str


class InterviewSessionUpdate(SQLModel):
    status: InterviewStatus | None = None
    completed_at: datetime | None = None
    transcript: str | None = None
    ai_feedback: str | None = None
    dialogue_history: list[dict[str, Any]] | None = None


class InterviewSessionRead(InterviewSessionBase):
    id: int
    started_at: datetime
    completed_at: datetime | None = None


class InterviewValidationResponse(SQLModel):
    can_interview: bool
    message: str


class LiveKitTokenResponse(SQLModel):
    token: str
    room_name: str
    server_url: str
    session_id: int
