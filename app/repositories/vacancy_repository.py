from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.models.vacancy import Vacancy, VacancyCreate, VacancyUpdate
from .base_repository import BaseRepository


class VacancyRepository(BaseRepository[Vacancy]):
    def __init__(self, session: AsyncSession):
        super().__init__(Vacancy, session)

    async def get_by_company(self, company_name: str) -> List[Vacancy]:
        statement = select(Vacancy).where(Vacancy.company_name == company_name)
        result = await self.session.execute(statement)
        return result.scalars().all()

    async def get_by_area(self, area_name: str) -> List[Vacancy]:
        statement = select(Vacancy).where(Vacancy.area_name == area_name)
        result = await self.session.execute(statement)
        return result.scalars().all()

    async def get_active_vacancies(self, skip: int = 0, limit: int = 100) -> List[Vacancy]:
        statement = (
            select(Vacancy)
            .where(Vacancy.is_archived == False)
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(statement)
        return result.scalars().all()

    async def search_vacancies(
        self,
        title: Optional[str] = None,
        company_name: Optional[str] = None,
        area_name: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Vacancy]:
        conditions = []
        
        if title:
            conditions.append(Vacancy.title.ilike(f"%{title}%"))
        if company_name:
            conditions.append(Vacancy.company_name.ilike(f"%{company_name}%"))
        if area_name:
            conditions.append(Vacancy.area_name.ilike(f"%{area_name}%"))
        
        statement = select(Vacancy)
        if conditions:
            statement = statement.where(and_(*conditions))
        
        statement = statement.offset(skip).limit(limit)
        result = await self.session.execute(statement)
        return result.scalars().all()