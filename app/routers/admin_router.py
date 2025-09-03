from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.interview_service import InterviewRoomService
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