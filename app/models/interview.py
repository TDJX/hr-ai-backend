from sqlmodel import SQLModel, Field, Column, Relationship
from sqlalchemy import Enum as SQLEnum, JSON
from datetime import datetime
from typing import Optional, List, Dict, Any
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
    status: str = Field(default="created", max_length=50)
    transcript: Optional[str] = None
    ai_feedback: Optional[str] = None
    dialogue_history: Optional[List[Dict[str, Any]]] = Field(default=None, sa_column=Column(JSON))
    # Добавляем отслеживание AI процесса
    ai_agent_pid: Optional[int] = None
    ai_agent_status: str = Field(default="not_started")  # not_started, running, stopped, failed


class InterviewSession(InterviewSessionBase, table=True):
    __tablename__ = "interview_sessions"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    # Связь с отчетом (один к одному)
    report: Optional["InterviewReport"] = Relationship(back_populates="interview_session")
    


class InterviewSessionCreate(SQLModel):
    resume_id: int
    room_name: str


class InterviewSessionUpdate(SQLModel):
    status: Optional[InterviewStatus] = None
    completed_at: Optional[datetime] = None
    transcript: Optional[str] = None
    ai_feedback: Optional[str] = None
    dialogue_history: Optional[List[Dict[str, Any]]] = None


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