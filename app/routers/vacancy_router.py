from fastapi import APIRouter, Depends, HTTPException, Query

from app.models.vacancy import VacancyCreate, VacancyRead, VacancyUpdate
from app.services.vacancy_service import VacancyService

router = APIRouter(prefix="/vacancies", tags=["vacancies"])


@router.post("/", response_model=VacancyRead)
async def create_vacancy(
    vacancy: VacancyCreate, vacancy_service: VacancyService = Depends(VacancyService)
):
    return await vacancy_service.create_vacancy(vacancy)


@router.get("/", response_model=list[VacancyRead])
async def get_vacancies(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    active_only: bool = Query(False),
    title: str | None = Query(None),
    company_name: str | None = Query(None),
    area_name: str | None = Query(None),
    vacancy_service: VacancyService = Depends(VacancyService),
):
    if any([title, company_name, area_name]):
        return await vacancy_service.search_vacancies(
            title=title,
            company_name=company_name,
            area_name=area_name,
            skip=skip,
            limit=limit,
        )

    if active_only:
        return await vacancy_service.get_active_vacancies(skip=skip, limit=limit)

    return await vacancy_service.get_all_vacancies(skip=skip, limit=limit)


@router.get("/{vacancy_id}", response_model=VacancyRead)
async def get_vacancy(
    vacancy_id: int, vacancy_service: VacancyService = Depends(VacancyService)
):
    vacancy = await vacancy_service.get_vacancy(vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    return vacancy


@router.put("/{vacancy_id}", response_model=VacancyRead)
async def update_vacancy(
    vacancy_id: int,
    vacancy: VacancyUpdate,
    vacancy_service: VacancyService = Depends(VacancyService),
):
    updated_vacancy = await vacancy_service.update_vacancy(vacancy_id, vacancy)
    if not updated_vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    return updated_vacancy


@router.delete("/{vacancy_id}")
async def delete_vacancy(
    vacancy_id: int, vacancy_service: VacancyService = Depends(VacancyService)
):
    success = await vacancy_service.delete_vacancy(vacancy_id)
    if not success:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    return {"message": "Vacancy deleted successfully"}


@router.patch("/{vacancy_id}/archive", response_model=VacancyRead)
async def archive_vacancy(
    vacancy_id: int, vacancy_service: VacancyService = Depends(VacancyService)
):
    archived_vacancy = await vacancy_service.archive_vacancy(vacancy_id)
    if not archived_vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    return archived_vacancy
