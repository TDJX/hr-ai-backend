from typing import List, Optional, Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from fastapi import Depends
from app.core.database import get_session
from app.models.vacancy import Vacancy, VacancyCreate, VacancyUpdate
from .base_repository import BaseRepository


class VacancyRepository(BaseRepository[Vacancy]):
    def __init__(self, session: Annotated[AsyncSession, Depends(get_session)]):
        super().__init__(Vacancy, session)

    async def get_by_company(self, company_name: str) -> List[Vacancy]:
        statement = select(Vacancy).where(Vacancy.company_name == company_name)
        result = await self._session.execute(statement)
        return result.scalars().all()

    async def get_active(self, skip: int = 0, limit: int = 100) -> List[Vacancy]:
        statement = (
            select(Vacancy)
            .where(Vacancy.is_archived == False)
            .offset(skip)
            .limit(limit)
        )
        result = await self._session.execute(statement)
        return result.scalars().all()

    async def search(
        self,
        title: Optional[str] = None,
        company_name: Optional[str] = None,
        area_name: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Vacancy]:
        """Поиск вакансий по критериям"""
        statement = select(Vacancy)
        conditions = []

        if title:
            conditions.append(Vacancy.title.ilike(f"%{title}%"))
        if company_name:
            conditions.append(Vacancy.company_name.ilike(f"%{company_name}%"))
        if area_name:
            conditions.append(Vacancy.area_name.ilike(f"%{area_name}%"))

        if conditions:
            statement = statement.where(and_(*conditions))

        statement = statement.offset(skip).limit(limit)
        result = await self._session.execute(statement)
        return result.scalars().all()


    async def get_active_vacancies(self, skip: int = 0, limit: int = 100) -> List[Vacancy]:
        """Получить активные вакансии (алиас для get_active)"""
        return await self.get_active(skip=skip, limit=limit)

    async def search_vacancies(
        self,
        title: Optional[str] = None,
        company_name: Optional[str] = None,
        area_name: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Vacancy]:
        """Поиск вакансий (алиас для search)"""
        return await self.search(
            title=title,
            company_name=company_name,
            area_name=area_name,
            skip=skip,
            limit=limit
        )

    async def archive(self, vacancy_id: int) -> Optional[Vacancy]:
        """Архивировать вакансию"""
        return await self.update(vacancy_id, {"is_active": False})