from datetime import datetime
from enum import Enum
from typing import Any, Optional

from sqlalchemy import JSON, Text
from sqlmodel import Column, Field, Relationship, SQLModel


class RecommendationType(str, Enum):
    STRONGLY_RECOMMEND = "strongly_recommend"
    RECOMMEND = "recommend"
    CONSIDER = "consider"
    REJECT = "reject"

    def __str__(self):
        return self.value


class InterviewReportBase(SQLModel):
    """Базовая модель отчета по интервью"""

    interview_session_id: int = Field(foreign_key="interview_sessions.id", unique=True)

    # Основные критерии оценки (0-100)
    technical_skills_score: int = Field(ge=0, le=100)
    technical_skills_justification: str | None = Field(default=None, max_length=1000)
    technical_skills_concerns: str | None = Field(default=None, max_length=500)

    experience_relevance_score: int = Field(ge=0, le=100)
    experience_relevance_justification: str | None = Field(
        default=None, max_length=1000
    )
    experience_relevance_concerns: str | None = Field(default=None, max_length=500)

    communication_score: int = Field(ge=0, le=100)
    communication_justification: str | None = Field(default=None, max_length=1000)
    communication_concerns: str | None = Field(default=None, max_length=500)

    problem_solving_score: int = Field(ge=0, le=100)
    problem_solving_justification: str | None = Field(default=None, max_length=1000)
    problem_solving_concerns: str | None = Field(default=None, max_length=500)

    cultural_fit_score: int = Field(ge=0, le=100)
    cultural_fit_justification: str | None = Field(default=None, max_length=1000)
    cultural_fit_concerns: str | None = Field(default=None, max_length=500)

    # Агрегированные поля
    overall_score: int = Field(ge=0, le=100)
    recommendation: RecommendationType

    # Дополнительные поля для анализа
    strengths: list[str] | None = Field(default=None, sa_column=Column(JSON))
    weaknesses: list[str] | None = Field(default=None, sa_column=Column(JSON))
    red_flags: list[str] | None = Field(default=None, sa_column=Column(JSON))

    # Метрики интервью
    questions_quality_score: float | None = Field(
        default=None, ge=0, le=10
    )  # Средняя оценка ответов
    interview_duration_minutes: int | None = Field(default=None, ge=0)
    response_count: int | None = Field(default=None, ge=0)
    dialogue_messages_count: int | None = Field(default=None, ge=0)

    # Дополнительная информация
    next_steps: str | None = Field(default=None, max_length=1000)
    interviewer_notes: str | None = Field(default=None, sa_column=Column(Text))

    # Детальный анализ вопросов (JSON)
    questions_analysis: list[dict[str, Any]] | None = Field(
        default=None, sa_column=Column(JSON)
    )

    # Метаданные анализа
    analysis_method: str | None = Field(
        default="openai_gpt4", max_length=50
    )  # openai_gpt4, fallback_heuristic
    llm_model_used: str | None = Field(default=None, max_length=100)
    analysis_duration_seconds: int | None = Field(default=None, ge=0)

    # PDF отчет
    pdf_report_url: str | None = Field(default=None, max_length=500)


class InterviewReport(InterviewReportBase, table=True):
    """Полный отчет по интервью с ID и временными метками"""

    __tablename__ = "interview_reports"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Связь с сессией интервью
    interview_session: Optional["InterviewSession"] = Relationship(
        back_populates="report"
    )


class InterviewReportCreate(SQLModel):
    """Модель для создания отчета"""

    interview_session_id: int

    technical_skills_score: int = Field(ge=0, le=100)
    technical_skills_justification: str | None = None
    technical_skills_concerns: str | None = None

    experience_relevance_score: int = Field(ge=0, le=100)
    experience_relevance_justification: str | None = None
    experience_relevance_concerns: str | None = None

    communication_score: int = Field(ge=0, le=100)
    communication_justification: str | None = None
    communication_concerns: str | None = None

    problem_solving_score: int = Field(ge=0, le=100)
    problem_solving_justification: str | None = None
    problem_solving_concerns: str | None = None

    cultural_fit_score: int = Field(ge=0, le=100)
    cultural_fit_justification: str | None = None
    cultural_fit_concerns: str | None = None

    overall_score: int = Field(ge=0, le=100)
    recommendation: RecommendationType

    strengths: list[str] | None = None
    weaknesses: list[str] | None = None
    red_flags: list[str] | None = None

    questions_quality_score: float | None = None
    interview_duration_minutes: int | None = None
    response_count: int | None = None
    dialogue_messages_count: int | None = None

    next_steps: str | None = None
    interviewer_notes: str | None = None
    questions_analysis: list[dict[str, Any]] | None = None

    analysis_method: str | None = "openai_gpt4"
    llm_model_used: str | None = None
    analysis_duration_seconds: int | None = None
    pdf_report_url: str | None = None


class InterviewReportUpdate(SQLModel):
    """Модель для обновления отчета"""

    technical_skills_score: int | None = Field(default=None, ge=0, le=100)
    technical_skills_justification: str | None = None
    technical_skills_concerns: str | None = None

    experience_relevance_score: int | None = Field(default=None, ge=0, le=100)
    experience_relevance_justification: str | None = None
    experience_relevance_concerns: str | None = None

    communication_score: int | None = Field(default=None, ge=0, le=100)
    communication_justification: str | None = None
    communication_concerns: str | None = None

    problem_solving_score: int | None = Field(default=None, ge=0, le=100)
    problem_solving_justification: str | None = None
    problem_solving_concerns: str | None = None

    cultural_fit_score: int | None = Field(default=None, ge=0, le=100)
    cultural_fit_justification: str | None = None
    cultural_fit_concerns: str | None = None

    overall_score: int | None = Field(default=None, ge=0, le=100)
    recommendation: RecommendationType | None = None

    strengths: list[str] | None = None
    weaknesses: list[str] | None = None
    red_flags: list[str] | None = None

    questions_quality_score: float | None = None
    interview_duration_minutes: int | None = None
    response_count: int | None = None
    dialogue_messages_count: int | None = None

    next_steps: str | None = None
    interviewer_notes: str | None = None
    questions_analysis: list[dict[str, Any]] | None = None

    analysis_method: str | None = None
    llm_model_used: str | None = None
    analysis_duration_seconds: int | None = None
    pdf_report_url: str | None = None


class InterviewReportRead(InterviewReportBase):
    """Модель для чтения отчета с ID и временными метками"""

    id: int
    created_at: datetime
    updated_at: datetime


class InterviewReportSummary(SQLModel):
    """Краткая сводка отчета для списков"""

    id: int
    interview_session_id: int
    overall_score: int
    recommendation: RecommendationType
    created_at: datetime

    # Основные баллы
    technical_skills_score: int
    experience_relevance_score: int
    communication_score: int
    problem_solving_score: int
    cultural_fit_score: int

    # Краткие выводы
    strengths: list[str] | None = None
    red_flags: list[str] | None = None


# Индексы для эффективных запросов по скорингу
"""
Полезные SQL индексы:
CREATE INDEX idx_interview_reports_overall_score ON interview_reports (overall_score DESC);
CREATE INDEX idx_interview_reports_recommendation ON interview_reports (recommendation);
CREATE INDEX idx_interview_reports_technical_skills ON interview_reports (technical_skills_score DESC);
CREATE INDEX idx_interview_reports_communication ON interview_reports (communication_score DESC);
CREATE INDEX idx_interview_reports_session_id ON interview_reports (interview_session_id);
"""
