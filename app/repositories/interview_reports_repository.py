from datetime import datetime
from typing import Annotated

from fastapi import Depends
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.interview_report import InterviewReport
from app.models.interview import InterviewSession
from app.models.resume import Resume
from app.models.vacancy import Vacancy
from app.repositories.base_repository import BaseRepository


class InterviewReportRepository(BaseRepository[InterviewReport]):
    def __init__(self, session: Annotated[AsyncSession, Depends(get_session)]):
        super().__init__(InterviewReport, session)

    async def get_by_session_id(self, session_id: int) -> InterviewReport | None:
        """Получить отчёт по ID сессии интервью"""
        statement = select(InterviewReport).where(
            InterviewReport.interview_session_id == session_id
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def update_scores(
        self,
        report_id: int,
        scores: dict,
    ) -> bool:
        """Обновить оценки в отчёте"""
        try:
            await self._session.execute(
                update(InterviewReport)
                .where(InterviewReport.id == report_id)
                .values(
                    **scores,
                    updated_at=datetime.utcnow(),
                )
            )
            await self._session.commit()
            return True
        except Exception:
            await self._session.rollback()
            return False

    async def update_pdf_url(self, report_id: int, pdf_url: str) -> bool:
        """Обновить ссылку на PDF отчёта"""
        try:
            await self._session.execute(
                update(InterviewReport)
                .where(InterviewReport.id == report_id)
                .values(pdf_report_url=pdf_url, updated_at=datetime.utcnow())
            )
            await self._session.commit()
            return True
        except Exception:
            await self._session.rollback()
            return False

    async def get_by_vacancy_id(self, vacancy_id: int) -> list[InterviewReport]:
        """Получить все отчёты по вакансии"""
        statement = (
            select(InterviewReport)
            .join(InterviewSession, InterviewSession.id == InterviewReport.interview_session_id)
            .join(Resume, Resume.id == InterviewSession.resume_id)
            .join(Vacancy, Vacancy.id == Resume.vacancy_id)
            .where(Vacancy.id == vacancy_id)
            .order_by(InterviewReport.overall_score.desc())
        )
        result = await self._session.execute(statement)
        return result.scalars().all()

    async def update_notes(self, report_id: int, notes: str) -> bool:
        """Обновить заметки интервьюера"""
        try:
            await self._session.execute(
                update(InterviewReport)
                .where(InterviewReport.id == report_id)
                .values(interviewer_notes=notes, updated_at=datetime.utcnow())
            )
            await self._session.commit()
            return True
        except Exception:
            await self._session.rollback()
            return False
