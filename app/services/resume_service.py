from typing import Annotated

from fastapi import Depends

from app.models.resume import Resume, ResumeCreate, ResumeStatus, ResumeUpdate
from app.repositories.resume_repository import ResumeRepository


class ResumeService:
    def __init__(
        self, repository: Annotated[ResumeRepository, Depends(ResumeRepository)]
    ):
        self.repository = repository

    async def create_resume(self, resume_data: ResumeCreate) -> Resume:
        resume = Resume.model_validate(resume_data)
        return await self.repository.create(resume)

    async def create_resume_with_session(
        self, resume_data: ResumeCreate, session_id: int
    ) -> Resume:
        """Создать резюме с привязкой к сессии"""
        resume_dict = resume_data.model_dump()
        return await self.repository.create_with_session(resume_dict, session_id)

    async def get_resume(self, resume_id: int) -> Resume | None:
        return await self.repository.get(resume_id)

    async def get_all_resumes(self, skip: int = 0, limit: int = 100) -> list[Resume]:
        return await self.repository.get_all(skip=skip, limit=limit)

    async def get_resumes_by_vacancy(self, vacancy_id: int) -> list[Resume]:
        return await self.repository.get_by_vacancy_id(vacancy_id)

    async def get_resumes_by_session(
        self, session_id: int, skip: int = 0, limit: int = 100
    ) -> list[Resume]:
        """Получить резюме пользователя по session_id"""
        return await self.repository.get_by_session_id(session_id)

    async def get_resumes_by_vacancy_and_session(
        self, vacancy_id: int, session_id: int
    ) -> list[Resume]:
        """Получить резюме пользователя для конкретной вакансии"""
        return await self.repository.get_by_vacancy_and_session(vacancy_id, session_id)

    async def get_resumes_by_status(self, status: ResumeStatus) -> list[Resume]:
        return await self.repository.get_by_status(status)

    async def update_resume(
        self, resume_id: int, resume_data: ResumeUpdate
    ) -> Resume | None:
        update_data = resume_data.model_dump(exclude_unset=True)
        if not update_data:
            return await self.repository.get(resume_id)
        return await self.repository.update(resume_id, update_data)

    async def delete_resume(self, resume_id: int) -> bool:
        return await self.repository.delete(resume_id)

    async def update_resume_status(
        self, resume_id: int, status: ResumeStatus
    ) -> Resume | None:
        return await self.repository.update_status(resume_id, status)

    async def add_interview_report(
        self, resume_id: int, report_url: str
    ) -> Resume | None:
        return await self.repository.add_interview_report(resume_id, report_url)
