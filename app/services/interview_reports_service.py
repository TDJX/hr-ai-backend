from datetime import datetime
from typing import Annotated

from fastapi import Depends

from app.models.interview_report import InterviewReport
from app.repositories.interview_reports_repository import InterviewReportRepository


class InterviewReportService:
    def __init__(
        self,
        report_repo: Annotated[
            InterviewReportRepository, Depends(InterviewReportRepository)
        ],
    ):
        self.report_repo = report_repo

    async def get_report_by_session(self, session_id: int) -> InterviewReport | None:
        """Получить отчёт по ID сессии"""
        return await self.report_repo.get_by_session_id(session_id)

    async def get_reports_by_vacancy(self, vacancy_id: int) -> list[InterviewReport]:
        """Получить все отчёты по вакансии"""
        return await self.report_repo.get_by_vacancy_id(vacancy_id)

    async def update_report_scores(self, report_id: int, scores: dict) -> bool:
        """
        Обновить оценки отчёта.
        Пример scores:
        {
            "technical_skills_score": 8,
            "communication_score": 7,
            "overall_score": 8
        }
        """
        return await self.report_repo.update_scores(report_id, scores)

    async def update_pdf_url(self, report_id: int, pdf_url: str) -> bool:
        """Обновить ссылку на PDF отчёта"""
        return await self.report_repo.update_pdf_url(report_id, pdf_url)

    async def update_interviewer_notes(self, report_id: int, notes: str) -> bool:
        """Обновить заметки интервьюера"""
        return await self.report_repo.update_notes(report_id, notes)

    async def create_report(
        self,
        interview_session_id: int,
        technical_skills_score: int,
        experience_relevance_score: int,
        communication_score: int,
        problem_solving_score: int,
        cultural_fit_score: int,
        overall_score: int,
        recommendation: str,
        strengths: dict | None = None,
        weaknesses: dict | None = None,
        red_flags: dict | None = None,
        next_steps: str | None = None,
        interviewer_notes: str | None = None,
        pdf_report_url: str | None = None,
    ) -> InterviewReport | None:
        """Создать новый отчёт для сессии"""
        try:
            report_data = {
                "interview_session_id": interview_session_id,
                "technical_skills_score": technical_skills_score,
                "experience_relevance_score": experience_relevance_score,
                "communication_score": communication_score,
                "problem_solving_score": problem_solving_score,
                "cultural_fit_score": cultural_fit_score,
                "overall_score": overall_score,
                "recommendation": recommendation,
                "strengths": strengths or {},
                "weaknesses": weaknesses or {},
                "red_flags": red_flags or {},
                "next_steps": next_steps,
                "interviewer_notes": interviewer_notes,
                "pdf_report_url": pdf_report_url,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
            return await self.report_repo.create(report_data)
        except Exception as e:
            print(f"Error creating interview report: {str(e)}")
            return None
