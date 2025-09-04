from typing import List, Optional, Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import Depends
from app.core.database import get_session
from app.models.resume import Resume, ResumeStatus
from .base_repository import BaseRepository


class ResumeRepository(BaseRepository[Resume]):
    def __init__(self, session: Annotated[AsyncSession, Depends(get_session)]):
        super().__init__(Resume, session)

    async def get_by_vacancy_id(self, vacancy_id: int) -> List[Resume]:
        statement = select(Resume).where(Resume.vacancy_id == vacancy_id)
        result = await self._session.execute(statement)
        return result.scalars().all()

    async def get_by_status(self, status: ResumeStatus) -> List[Resume]:
        statement = select(Resume).where(Resume.status == status)
        result = await self._session.execute(statement)
        return result.scalars().all()

    async def get_by_id(self, resume_id: int) -> Optional[Resume]:
        """Получить резюме по ID"""
        return await self.get(resume_id)

    async def create_with_session(self, resume_dict: dict, session_id: int) -> Resume:
        """Создать резюме с привязкой к сессии"""
        resume_dict['session_id'] = session_id
        return await self.create(resume_dict)

    async def get_by_session_id(self, session_id: int) -> List[Resume]:
        """Получить резюме по session_id"""
        statement = select(Resume).where(Resume.session_id == session_id)
        result = await self._session.execute(statement)
        return result.scalars().all()

    async def get_by_vacancy_and_session(self, vacancy_id: int, session_id: int) -> List[Resume]:
        """Получить резюме по vacancy_id и session_id"""
        statement = select(Resume).where(
            Resume.vacancy_id == vacancy_id,
            Resume.session_id == session_id
        )
        result = await self._session.execute(statement)
        return result.scalars().all()

    async def update_status(self, resume_id: int, status: ResumeStatus) -> Optional[Resume]:
        """Обновить статус резюме"""
        return await self.update(resume_id, {"status": status})

    async def add_interview_report(self, resume_id: int, report_url: str) -> Optional[Resume]:
        """Добавить ссылку на отчет интервью"""
        return await self.update(resume_id, {"interview_report_url": report_url})

