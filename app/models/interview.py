from sqlmodel import SQLModel, Field, Column
from sqlalchemy import Enum as SQLEnum, String
from datetime import datetime
from typing import Optional
from enum import Enum


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
    status: str = Field(
        default="created",
        sa_column=Column(SQLEnum('created', 'active', 'completed', 'failed', name="interviewstatus"))
    )
    transcript: Optional[str] = None
    ai_feedback: Optional[str] = None
    # Добавляем отслеживание AI процесса
    ai_agent_pid: Optional[int] = None
    ai_agent_status: str = Field(default="not_started")  # not_started, running, stopped, failed


class InterviewSession(InterviewSessionBase, table=True):
    __tablename__ = "interview_sessions"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


class InterviewSessionCreate(SQLModel):
    resume_id: int
    room_name: str


class InterviewSessionUpdate(SQLModel):
    status: Optional[InterviewStatus] = None
    completed_at: Optional[datetime] = None
    transcript: Optional[str] = None
    ai_feedback: Optional[str] = None


class InterviewSessionRead(InterviewSessionBase):
    id: int
    started_at: datetime
    completed_at: Optional[datetime] = None


class InterviewValidationResponse(SQLModel):
    can_interview: bool
    message: str


class LiveKitTokenResponse(SQLModel):
    token: str
    room_name: str
    server_url: str