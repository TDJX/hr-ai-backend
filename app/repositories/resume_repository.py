from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.resume import Resume, ResumeStatus
from .base_repository import BaseRepository


class ResumeRepository(BaseRepository[Resume]):
    def __init__(self, session: AsyncSession):
        super().__init__(Resume, session)

    async def get_by_vacancy_id(self, vacancy_id: int) -> List[Resume]:
        statement = select(Resume).where(Resume.vacancy_id == vacancy_id)
        result = await self.session.execute(statement)
        return result.scalars().all()

    async def get_by_session_id(self, session_id: int) -> List[Resume]:
        """Получить все резюме пользователя по session_id"""
        statement = select(Resume).where(Resume.session_id == session_id)
        result = await self.session.execute(statement)
        return result.scalars().all()

    async def get_by_vacancy_and_session(self, vacancy_id: int, session_id: int) -> List[Resume]:
        """Получить резюме пользователя для конкретной вакансии"""
        statement = select(Resume).where(
            Resume.vacancy_id == vacancy_id,
            Resume.session_id == session_id
        )
        result = await self.session.execute(statement)
        return result.scalars().all()

    async def get_by_status(self, status: ResumeStatus) -> List[Resume]:
        statement = select(Resume).where(Resume.status == status)
        result = await self.session.execute(statement)
        return result.scalars().all()

    async def get_by_applicant_email(self, email: str) -> List[Resume]:
        statement = select(Resume).where(Resume.applicant_email == email)
        result = await self.session.execute(statement)
        return result.scalars().all()

    async def create_with_session(self, resume_data: dict, session_id: int) -> Resume:
        """Создать резюме с привязкой к сессии"""
        resume_data['session_id'] = session_id
        new_resume = Resume(**resume_data)
        return await self.create(new_resume)

    async def update_status(self, resume_id: int, status: ResumeStatus) -> Optional[Resume]:
        return await self.update(resume_id, {"status": status})

    async def add_interview_report(self, resume_id: int, report_url: str) -> Optional[Resume]:
        return await self.update(resume_id, {
            "interview_report_url": report_url,
            "status": ResumeStatus.INTERVIEWED
        })