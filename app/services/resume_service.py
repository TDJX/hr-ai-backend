from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.resume import Resume, ResumeCreate, ResumeUpdate, ResumeStatus
from app.repositories.resume_repository import ResumeRepository


class ResumeService:
    def __init__(self, session: AsyncSession):
        self.repository = ResumeRepository(session)

    async def create_resume(self, resume_data: ResumeCreate) -> Resume:
        resume = Resume.model_validate(resume_data)
        return await self.repository.create(resume)

    async def create_resume_with_session(self, resume_data: ResumeCreate, session_id: int) -> Resume:
        """Создать резюме с привязкой к сессии"""
        resume_dict = resume_data.model_dump()
        return await self.repository.create_with_session(resume_dict, session_id)

    async def get_resume(self, resume_id: int) -> Optional[Resume]:
        return await self.repository.get(resume_id)

    async def get_all_resumes(self, skip: int = 0, limit: int = 100) -> List[Resume]:
        return await self.repository.get_all(skip=skip, limit=limit)

    async def get_resumes_by_vacancy(self, vacancy_id: int) -> List[Resume]:
        return await self.repository.get_by_vacancy_id(vacancy_id)

    async def get_resumes_by_session(self, session_id: int, skip: int = 0, limit: int = 100) -> List[Resume]:
        """Получить резюме пользователя по session_id"""
        return await self.repository.get_by_session_id(session_id)

    async def get_resumes_by_vacancy_and_session(self, vacancy_id: int, session_id: int) -> List[Resume]:
        """Получить резюме пользователя для конкретной вакансии"""
        return await self.repository.get_by_vacancy_and_session(vacancy_id, session_id)

    async def get_resumes_by_status(self, status: ResumeStatus) -> List[Resume]:
        return await self.repository.get_by_status(status)

    async def update_resume(self, resume_id: int, resume_data: ResumeUpdate) -> Optional[Resume]:
        update_data = resume_data.model_dump(exclude_unset=True)
        if not update_data:
            return await self.repository.get(resume_id)
        return await self.repository.update(resume_id, update_data)

    async def delete_resume(self, resume_id: int) -> bool:
        return await self.repository.delete(resume_id)

    async def update_resume_status(self, resume_id: int, status: ResumeStatus) -> Optional[Resume]:
        return await self.repository.update_status(resume_id, status)

    async def add_interview_report(self, resume_id: int, report_url: str) -> Optional[Resume]:
        return await self.repository.add_interview_report(resume_id, report_url)