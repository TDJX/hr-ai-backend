from datetime import datetime
from enum import Enum

from sqlalchemy import JSON
from sqlmodel import Column, Field, SQLModel


class ResumeStatus(str, Enum):
    PENDING = "pending"
    PARSING = "parsing"
    PARSED = "parsed"
    PARSE_FAILED = "parse_failed"
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
    applicant_phone: str | None = Field(max_length=50)
    resume_file_url: str
    cover_letter: str | None = None
    status: ResumeStatus = Field(default=ResumeStatus.PENDING)
    interview_report_url: str | None = None
    notes: str | None = None
    parsed_data: dict | None = Field(default=None, sa_column=Column(JSON))
    interview_plan: dict | None = Field(default=None, sa_column=Column(JSON))
    parse_error: str | None = None


class Resume(ResumeBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ResumeCreate(SQLModel):
    vacancy_id: int
    applicant_name: str = Field(max_length=255)
    applicant_email: str = Field(max_length=255)
    applicant_phone: str | None = Field(max_length=50)
    resume_file_url: str
    cover_letter: str | None = None


class ResumeUpdate(SQLModel):
    applicant_name: str | None = None
    applicant_email: str | None = None
    applicant_phone: str | None = None
    cover_letter: str | None = None
    status: ResumeStatus | None = None
    interview_report_url: str | None = None
    notes: str | None = None
    parsed_data: dict | None = None
    interview_plan: dict | None = None
    parse_error: str | None = None


class ResumeRead(ResumeBase):
    id: int
    created_at: datetime
    updated_at: datetime
