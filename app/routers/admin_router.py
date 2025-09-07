import json
import os
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException

from app.services.admin_service import AdminService
from app.services.agent_manager import agent_manager

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/interview-processes")
async def list_active_interview_processes(
    admin_service: AdminService = Depends(AdminService),
) -> dict:
    """Список всех активных AI процессов интервью"""
    return await admin_service.get_active_interview_processes()


@router.post("/interview-processes/{session_id}/stop")
async def stop_interview_process(
    session_id: int, admin_service: AdminService = Depends(AdminService)
) -> dict:
    """Остановить AI процесс для конкретного интервью"""
    result = await admin_service.stop_interview_process(session_id)

    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["message"])

    return result


@router.post("/interview-processes/cleanup")
async def cleanup_dead_processes(
    admin_service: AdminService = Depends(AdminService),
) -> dict:
    """Очистка мертвых процессов"""
    return await admin_service.cleanup_dead_processes()


@router.get("/system-stats")
async def get_system_stats(admin_service: AdminService = Depends(AdminService)) -> dict:
    """Общая статистика системы"""
    result = await admin_service.get_system_stats()

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return result


@router.get("/agent/status")
async def get_agent_status() -> dict:
    """Статус AI агента"""
    return {"agent": agent_manager.get_status()}


@router.post("/agent/start")
async def start_agent() -> dict:
    """Запуск AI агента"""
    success = await agent_manager.start_agent()

    if success:
        return {"success": True, "message": "AI Agent started successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to start AI Agent")


@router.post("/agent/stop")
async def stop_agent() -> dict:
    """Остановка AI агента"""
    success = await agent_manager.stop_agent()

    if success:
        return {"success": True, "message": "AI Agent stopped successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to stop AI Agent")


@router.post("/agent/restart")
async def restart_agent() -> dict:
    """Перезапуск AI агента"""
    # Сначала останавливаем
    await agent_manager.stop_agent()

    # Затем запускаем
    success = await agent_manager.start_agent()

    if success:
        return {"success": True, "message": "AI Agent restarted successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to restart AI Agent")


@router.get("/analytics/dashboard")
async def get_analytics_dashboard(
    admin_service: AdminService = Depends(AdminService),
) -> dict:
    """Основная аналитическая панель"""
    return await admin_service.get_analytics_dashboard()


@router.get("/analytics/candidates/{vacancy_id}")
async def get_vacancy_analytics(
    vacancy_id: int, admin_service: AdminService = Depends(AdminService)
) -> dict:
    """Аналитика кандидатов по конкретной вакансии"""
    return await admin_service.get_vacancy_analytics(vacancy_id)


@router.post("/analytics/generate-reports/{vacancy_id}")
async def generate_reports_for_vacancy(
    vacancy_id: int, admin_service: AdminService = Depends(AdminService)
) -> dict:
    """Запустить генерацию отчетов для всех кандидатов вакансии"""
    result = await admin_service.generate_reports_for_vacancy(vacancy_id)

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


@router.post("/interview/{session_id}/force-end")
async def force_end_interview(session_id: int) -> dict:
    """Принудительно завершить активное интервью"""
    try:
        # Получаем статус агента
        agent_status = agent_manager.get_status()
        
        if agent_status["status"] != "active":
            raise HTTPException(
                status_code=400, 
                detail=f"Agent is not active, current status: {agent_status['status']}"
            )
        
        if agent_status["session_id"] != session_id:
            raise HTTPException(
                status_code=400,
                detail=f"Agent is not handling session {session_id}, current session: {agent_status['session_id']}"
            )
        
        # Записываем команду завершения в файл команд
        command_file = "agent_commands.json"
        end_command = {
            "action": "end_session",
            "session_id": session_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "initiated_by": "admin_api"
        }
        
        with open(command_file, "w", encoding="utf-8") as f:
            json.dump(end_command, f, ensure_ascii=False, indent=2)
        
        return {
            "success": True,
            "message": f"Force end command sent for session {session_id}",
            "session_id": session_id,
            "command_file": command_file
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send force end command: {str(e)}"
        )
