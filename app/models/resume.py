from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime
from enum import Enum


class ResumeStatus(str, Enum):
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    INTERVIEW_SCHEDULED = "interview_scheduled"
    INTERVIEWED = "interviewed"
    REJECTED = "rejected"
    ACCEPTED = "accepted"


class ResumeBase(SQLModel):
    vacancy_id: int = Field(foreign_key="vacancy.id")
    session_id: int = Field(foreign_key="session.id")
    applicant_name: str = Field(max_length=255)
    applicant_email: str = Field(max_length=255)
    applicant_phone: Optional[str] = Field(max_length=50)
    resume_file_url: str
    cover_letter: Optional[str] = None
    status: ResumeStatus = Field(default=ResumeStatus.PENDING)
    interview_report_url: Optional[str] = None
    notes: Optional[str] = None


class Resume(ResumeBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ResumeCreate(SQLModel):
    vacancy_id: int
    applicant_name: str = Field(max_length=255)
    applicant_email: str = Field(max_length=255)
    applicant_phone: Optional[str] = Field(max_length=50)
    resume_file_url: str
    cover_letter: Optional[str] = None


class ResumeUpdate(SQLModel):
    applicant_name: Optional[str] = None
    applicant_email: Optional[str] = None
    applicant_phone: Optional[str] = None
    cover_letter: Optional[str] = None
    status: Optional[ResumeStatus] = None
    interview_report_url: Optional[str] = None
    notes: Optional[str] = None


class ResumeRead(ResumeBase):
    id: int
    created_at: datetime
    updated_at: datetime