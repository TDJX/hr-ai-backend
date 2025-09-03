from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.interview_service import InterviewRoomService
from app.services.agent_manager import agent_manager, AgentStatus
from typing import List, Dict
import psutil

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/interview-processes")
async def list_active_interview_processes(db: AsyncSession = Depends(get_db)) -> Dict:
    """Список всех активных AI процессов интервью"""
    interview_service = InterviewRoomService(db)
    
    active_sessions = await interview_service.get_active_agent_processes()
    
    processes_info = []
    for session in active_sessions:
        process_info = {
            "session_id": session.id,
            "resume_id": session.resume_id,
            "room_name": session.room_name,
            "pid": session.ai_agent_pid,
            "status": session.ai_agent_status,
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "is_running": False,
            "memory_mb": 0,
            "cpu_percent": 0
        }
        
        # Проверяем реальное состояние процесса
        if session.ai_agent_pid:
            try:
                process = psutil.Process(session.ai_agent_pid)
                if process.is_running():
                    process_info["is_running"] = True
                    process_info["memory_mb"] = round(process.memory_info().rss / 1024 / 1024, 1)
                    process_info["cpu_percent"] = round(process.cpu_percent(), 1)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        processes_info.append(process_info)
    
    return {
        "total_active_sessions": len(active_sessions),
        "processes": processes_info
    }


@router.post("/interview-processes/{session_id}/stop")
async def stop_interview_process(session_id: int, db: AsyncSession = Depends(get_db)) -> Dict:
    """Остановить AI процесс для конкретного интервью"""
    interview_service = InterviewRoomService(db)
    
    success = await interview_service.stop_agent_process(session_id)
    
    if success:
        return {"message": f"AI process for session {session_id} stopped successfully"}
    else:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found or process not running")


@router.post("/interview-processes/cleanup")
async def cleanup_dead_processes(db: AsyncSession = Depends(get_db)) -> Dict:
    """Очистка мертвых процессов"""
    interview_service = InterviewRoomService(db)
    
    cleaned_count = await interview_service.cleanup_dead_processes()
    
    return {
        "message": f"Cleaned up {cleaned_count} dead processes"
    }


@router.get("/system-stats")
async def get_system_stats() -> Dict:
    """Общая статистика системы"""
    try:
        # Общая информация о системе
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Поиск всех Python процессов (потенциальные AI агенты)
        python_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'cpu_percent', 'cmdline']):
            try:
                if proc.info['name'] and 'python' in proc.info['name'].lower():
                    cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                    if 'ai_interviewer_agent' in cmdline:
                        python_processes.append({
                            'pid': proc.info['pid'],
                            'memory_mb': round(proc.info['memory_info'].rss / 1024 / 1024, 1),
                            'cpu_percent': proc.info['cpu_percent'] or 0,
                            'cmdline': cmdline
                        })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        return {
            "system": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available_gb": round(memory.available / 1024 / 1024 / 1024, 1),
                "disk_percent": disk.percent,
                "disk_free_gb": round(disk.free / 1024 / 1024 / 1024, 1)
            },
            "ai_agents": {
                "count": len(python_processes),
                "total_memory_mb": sum(p['memory_mb'] for p in python_processes),
                "processes": python_processes
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting system stats: {str(e)}")


# Новые endpoints для управления AI агентом
@router.get("/agent/status")
async def get_agent_status():
    """Получить подробный статус AI агента"""
    return agent_manager.get_status()


@router.post("/agent/start")
async def start_agent():
    """Запустить AI агента (если не запущен)"""
    if agent_manager.get_status()["process_alive"]:
        return {"message": "Agent is already running", "status": agent_manager.status.value}
    
    success = await agent_manager.start_agent_process()
    return {
        "success": success,
        "message": "Agent started successfully" if success else "Failed to start agent",
        "status": agent_manager.status.value
    }


@router.post("/agent/stop")
async def stop_agent():
    """Остановить AI агента"""
    if not agent_manager.get_status()["process_alive"]:
        return {"message": "Agent is not running", "status": agent_manager.status.value}
    
    success = await agent_manager.stop_agent_process()
    return {
        "success": success,
        "message": "Agent stopped successfully" if success else "Failed to stop agent",
        "status": agent_manager.status.value
    }


@router.post("/agent/restart")
async def restart_agent():
    """Перезапустить AI агента"""
    # Останавливаем если запущен
    if agent_manager.get_status()["process_alive"]:
        stop_success = await agent_manager.stop_agent_process()
        if not stop_success:
            return {
                "success": False,
                "message": "Failed to stop agent for restart",
                "status": agent_manager.status.value
            }
    
    # Запускаем заново
    start_success = await agent_manager.start_agent_process()
    return {
        "success": start_success,
        "message": "Agent restarted successfully" if start_success else "Failed to restart agent",
        "status": agent_manager.status.value
    }


@router.get("/interviews/active")
async def get_active_interviews():
    """Получить информацию об активных интервью"""
    agent_status = agent_manager.get_status()
    
    return {
        "active_interview_count": 1 if agent_status["current_interview_id"] else 0,
        "current_interview_id": agent_status["current_interview_id"],
        "agent_status": agent_status["status"],
        "process_info": {
            "pid": agent_status["process_pid"],
            "alive": agent_status["process_alive"]
        },
        "queue_info": agent_status["queue_sizes"]
    }


@router.post("/interviews/{interview_id}/force-stop")
async def force_stop_interview(interview_id: int):
    """Принудительно остановить интервью"""
    current_interview = agent_manager.current_interview_id
    
    if current_interview != interview_id:
        return {
            "success": False,
            "message": f"Interview {interview_id} is not currently active. Active: {current_interview}"
        }
    
    success = await agent_manager.stop_interview()
    return {
        "success": success,
        "message": f"Interview {interview_id} force-stopped" if success else "Failed to force-stop interview",
        "agent_status": agent_manager.status.value
    }


@router.get("/system/health") 
async def system_health():
    """Проверка здоровья системы"""
    agent_status = agent_manager.get_status()
    
    health_status = "healthy"
    issues = []
    
    if not agent_status["process_alive"]:
        health_status = "unhealthy"
        issues.append("AI Agent process is not running")
    elif agent_status["status"] == AgentStatus.ERROR.value:
        health_status = "degraded"
        issues.append("AI Agent is in error state")
    
    # Проверяем размеры очередей
    if agent_status["queue_sizes"]["commands"] > 50:
        health_status = "degraded"
        issues.append("Command queue is getting full")
        
    if agent_status["queue_sizes"]["responses"] > 50:
        health_status = "degraded" 
        issues.append("Response queue is getting full")
    
    return {
        "status": health_status,
        "timestamp": agent_manager.get_status(),
        "agent_info": agent_status,
        "issues": issues,
        "recommendations": [
            "Restart agent if in error state",
            "Monitor queue sizes",
            "Check system resources"
        ] if issues else []
    }