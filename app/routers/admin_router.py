from fastapi import APIRouter, Depends, HTTPException
from app.services.admin_service import AdminService
from typing import Dict

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/interview-processes")
async def list_active_interview_processes(
    admin_service: AdminService = Depends(AdminService)
) -> Dict:
    """Список всех активных AI процессов интервью"""
    return await admin_service.get_active_interview_processes()


@router.post("/interview-processes/{session_id}/stop")
async def stop_interview_process(
    session_id: int, 
    admin_service: AdminService = Depends(AdminService)
) -> Dict:
    """Остановить AI процесс для конкретного интервью"""
    result = await admin_service.stop_interview_process(session_id)
    
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["message"])
    
    return result


@router.post("/interview-processes/cleanup")
async def cleanup_dead_processes(
    admin_service: AdminService = Depends(AdminService)
) -> Dict:
    """Очистка мертвых процессов"""
    return await admin_service.cleanup_dead_processes()


@router.get("/system-stats")
async def get_system_stats(
    admin_service: AdminService = Depends(AdminService)
) -> Dict:
    """Общая статистика системы"""
    result = await admin_service.get_system_stats()
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    
    return result


@router.get("/analytics/dashboard")
async def get_analytics_dashboard(
    admin_service: AdminService = Depends(AdminService)
) -> Dict:
    """Основная аналитическая панель"""
    return await admin_service.get_analytics_dashboard()


@router.get("/analytics/candidates/{vacancy_id}")
async def get_vacancy_analytics(
    vacancy_id: int, 
    admin_service: AdminService = Depends(AdminService)
) -> Dict:
    """Аналитика кандидатов по конкретной вакансии"""
    return await admin_service.get_vacancy_analytics(vacancy_id)


@router.post("/analytics/generate-reports/{vacancy_id}")
async def generate_reports_for_vacancy(
    vacancy_id: int, 
    admin_service: AdminService = Depends(AdminService)
) -> Dict:
    """Запустить генерацию отчетов для всех кандидатов вакансии"""
    result = await admin_service.generate_reports_for_vacancy(vacancy_id)
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result