# -*- coding: utf-8 -*-
from sqlmodel import SQLModel, Field, Column, Relationship
from sqlalchemy import JSON, String, Integer, Float, Text
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


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
    technical_skills_justification: Optional[str] = Field(default=None, max_length=1000)
    technical_skills_concerns: Optional[str] = Field(default=None, max_length=500)
    
    experience_relevance_score: int = Field(ge=0, le=100)
    experience_relevance_justification: Optional[str] = Field(default=None, max_length=1000)
    experience_relevance_concerns: Optional[str] = Field(default=None, max_length=500)
    
    communication_score: int = Field(ge=0, le=100)
    communication_justification: Optional[str] = Field(default=None, max_length=1000)
    communication_concerns: Optional[str] = Field(default=None, max_length=500)
    
    problem_solving_score: int = Field(ge=0, le=100)
    problem_solving_justification: Optional[str] = Field(default=None, max_length=1000)
    problem_solving_concerns: Optional[str] = Field(default=None, max_length=500)
    
    cultural_fit_score: int = Field(ge=0, le=100)
    cultural_fit_justification: Optional[str] = Field(default=None, max_length=1000)
    cultural_fit_concerns: Optional[str] = Field(default=None, max_length=500)
    
    # Агрегированные поля
    overall_score: int = Field(ge=0, le=100)
    recommendation: RecommendationType
    
    # Дополнительные поля для анализа
    strengths: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    weaknesses: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    red_flags: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    
    # Метрики интервью
    questions_quality_score: Optional[float] = Field(default=None, ge=0, le=10)  # Средняя оценка ответов
    interview_duration_minutes: Optional[int] = Field(default=None, ge=0)
    response_count: Optional[int] = Field(default=None, ge=0)
    dialogue_messages_count: Optional[int] = Field(default=None, ge=0)
    
    # Дополнительная информация
    next_steps: Optional[str] = Field(default=None, max_length=1000)
    interviewer_notes: Optional[str] = Field(default=None, sa_column=Column(Text))
    
    # Детальный анализ вопросов (JSON)
    questions_analysis: Optional[List[Dict[str, Any]]] = Field(default=None, sa_column=Column(JSON))
    
    # Метаданные анализа
    analysis_method: Optional[str] = Field(default="openai_gpt4", max_length=50)  # openai_gpt4, fallback_heuristic
    llm_model_used: Optional[str] = Field(default=None, max_length=100)
    analysis_duration_seconds: Optional[int] = Field(default=None, ge=0)


class InterviewReport(InterviewReportBase, table=True):
    """Полный отчет по интервью с ID и временными метками"""
    __tablename__ = "interview_reports"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Связь с сессией интервью
    interview_session: Optional["InterviewSession"] = Relationship(back_populates="report")


class InterviewReportCreate(SQLModel):
    """Модель для создания отчета"""
    interview_session_id: int
    
    technical_skills_score: int = Field(ge=0, le=100)
    technical_skills_justification: Optional[str] = None
    technical_skills_concerns: Optional[str] = None
    
    experience_relevance_score: int = Field(ge=0, le=100)
    experience_relevance_justification: Optional[str] = None
    experience_relevance_concerns: Optional[str] = None
    
    communication_score: int = Field(ge=0, le=100)
    communication_justification: Optional[str] = None
    communication_concerns: Optional[str] = None
    
    problem_solving_score: int = Field(ge=0, le=100)
    problem_solving_justification: Optional[str] = None
    problem_solving_concerns: Optional[str] = None
    
    cultural_fit_score: int = Field(ge=0, le=100)
    cultural_fit_justification: Optional[str] = None
    cultural_fit_concerns: Optional[str] = None
    
    overall_score: int = Field(ge=0, le=100)
    recommendation: RecommendationType
    
    strengths: Optional[List[str]] = None
    weaknesses: Optional[List[str]] = None
    red_flags: Optional[List[str]] = None
    
    questions_quality_score: Optional[float] = None
    interview_duration_minutes: Optional[int] = None
    response_count: Optional[int] = None
    dialogue_messages_count: Optional[int] = None
    
    next_steps: Optional[str] = None
    interviewer_notes: Optional[str] = None
    questions_analysis: Optional[List[Dict[str, Any]]] = None
    
    analysis_method: Optional[str] = "openai_gpt4"
    llm_model_used: Optional[str] = None
    analysis_duration_seconds: Optional[int] = None


class InterviewReportUpdate(SQLModel):
    """Модель для обновления отчета"""
    technical_skills_score: Optional[int] = Field(default=None, ge=0, le=100)
    technical_skills_justification: Optional[str] = None
    technical_skills_concerns: Optional[str] = None
    
    experience_relevance_score: Optional[int] = Field(default=None, ge=0, le=100)
    experience_relevance_justification: Optional[str] = None
    experience_relevance_concerns: Optional[str] = None
    
    communication_score: Optional[int] = Field(default=None, ge=0, le=100)
    communication_justification: Optional[str] = None
    communication_concerns: Optional[str] = None
    
    problem_solving_score: Optional[int] = Field(default=None, ge=0, le=100)
    problem_solving_justification: Optional[str] = None
    problem_solving_concerns: Optional[str] = None
    
    cultural_fit_score: Optional[int] = Field(default=None, ge=0, le=100)
    cultural_fit_justification: Optional[str] = None
    cultural_fit_concerns: Optional[str] = None
    
    overall_score: Optional[int] = Field(default=None, ge=0, le=100)
    recommendation: Optional[RecommendationType] = None
    
    strengths: Optional[List[str]] = None
    weaknesses: Optional[List[str]] = None
    red_flags: Optional[List[str]] = None
    
    questions_quality_score: Optional[float] = None
    interview_duration_minutes: Optional[int] = None
    response_count: Optional[int] = None
    dialogue_messages_count: Optional[int] = None
    
    next_steps: Optional[str] = None
    interviewer_notes: Optional[str] = None
    questions_analysis: Optional[List[Dict[str, Any]]] = None
    
    analysis_method: Optional[str] = None
    llm_model_used: Optional[str] = None
    analysis_duration_seconds: Optional[int] = None


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
    strengths: Optional[List[str]] = None
    red_flags: Optional[List[str]] = None


# Индексы для эффективных запросов по скорингу
"""
Полезные SQL индексы:
CREATE INDEX idx_interview_reports_overall_score ON interview_reports (overall_score DESC);
CREATE INDEX idx_interview_reports_recommendation ON interview_reports (recommendation);
CREATE INDEX idx_interview_reports_technical_skills ON interview_reports (technical_skills_score DESC);
CREATE INDEX idx_interview_reports_communication ON interview_reports (communication_score DESC);
CREATE INDEX idx_interview_reports_session_id ON interview_reports (interview_session_id);
"""