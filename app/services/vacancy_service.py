from typing import Annotated

from fastapi import Depends

from app.models.vacancy import Vacancy, VacancyCreate, VacancyUpdate
from app.repositories.vacancy_repository import VacancyRepository


class VacancyService:
    def __init__(
        self, repository: Annotated[VacancyRepository, Depends(VacancyRepository)]
    ):
        self.repository = repository

    async def create_vacancy(self, vacancy_data: VacancyCreate) -> Vacancy:
        vacancy = Vacancy.model_validate(vacancy_data)
        return await self.repository.create(vacancy)

    async def get_vacancy(self, vacancy_id: int) -> Vacancy | None:
        return await self.repository.get(vacancy_id)

    async def get_all_vacancies(self, skip: int = 0, limit: int = 100) -> list[Vacancy]:
        return await self.repository.get_all(skip=skip, limit=limit)

    async def get_active_vacancies(
        self, skip: int = 0, limit: int = 100
    ) -> list[Vacancy]:
        return await self.repository.get_active_vacancies(skip=skip, limit=limit)

    async def update_vacancy(
        self, vacancy_id: int, vacancy_data: VacancyUpdate
    ) -> Vacancy | None:
        update_data = vacancy_data.model_dump(exclude_unset=True)
        if not update_data:
            return await self.repository.get(vacancy_id)
        return await self.repository.update(vacancy_id, update_data)

    async def delete_vacancy(self, vacancy_id: int) -> bool:
        return await self.repository.delete(vacancy_id)

    async def archive_vacancy(self, vacancy_id: int) -> Vacancy | None:
        return await self.repository.update(vacancy_id, {"is_archived": True})

    async def search_vacancies(
        self,
        title: str | None = None,
        company_name: str | None = None,
        area_name: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Vacancy]:
        return await self.repository.search_vacancies(
            title=title,
            company_name=company_name,
            area_name=area_name,
            skip=skip,
            limit=limit,
        )
