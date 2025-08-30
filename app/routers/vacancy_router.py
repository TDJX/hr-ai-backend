from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.core.database import get_session
from app.models.vacancy import VacancyCreate, VacancyUpdate, VacancyRead
from app.services.vacancy_service import VacancyService

router = APIRouter(prefix="/vacancies", tags=["vacancies"])


@router.post("/", response_model=VacancyRead)
async def create_vacancy(
    vacancy: VacancyCreate,
    session: AsyncSession = Depends(get_session)
):
    service = VacancyService(session)
    return await service.create_vacancy(vacancy)


@router.get("/", response_model=List[VacancyRead])
async def get_vacancies(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    active_only: bool = Query(False),
    title: Optional[str] = Query(None),
    company_name: Optional[str] = Query(None),
    area_name: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session)
):
    service = VacancyService(session)
    
    if any([title, company_name, area_name]):
        return await service.search_vacancies(
            title=title,
            company_name=company_name,
            area_name=area_name,
            skip=skip,
            limit=limit
        )
    
    if active_only:
        return await service.get_active_vacancies(skip=skip, limit=limit)
    
    return await service.get_all_vacancies(skip=skip, limit=limit)


@router.get("/{vacancy_id}", response_model=VacancyRead)
async def get_vacancy(
    vacancy_id: int,
    session: AsyncSession = Depends(get_session)
):
    service = VacancyService(session)
    vacancy = await service.get_vacancy(vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    return vacancy


@router.put("/{vacancy_id}", response_model=VacancyRead)
async def update_vacancy(
    vacancy_id: int,
    vacancy: VacancyUpdate,
    session: AsyncSession = Depends(get_session)
):
    service = VacancyService(session)
    updated_vacancy = await service.update_vacancy(vacancy_id, vacancy)
    if not updated_vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    return updated_vacancy


@router.delete("/{vacancy_id}")
async def delete_vacancy(
    vacancy_id: int,
    session: AsyncSession = Depends(get_session)
):
    service = VacancyService(session)
    success = await service.delete_vacancy(vacancy_id)
    if not success:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    return {"message": "Vacancy deleted successfully"}


@router.patch("/{vacancy_id}/archive", response_model=VacancyRead)
async def archive_vacancy(
    vacancy_id: int,
    session: AsyncSession = Depends(get_session)
):
    service = VacancyService(session)
    archived_vacancy = await service.archive_vacancy(vacancy_id)
    if not archived_vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    return archived_vacancy