from typing import Dict, List, Annotated
from fastapi import Depends

from app.repositories.interview_repository import InterviewRepository
from app.repositories.resume_repository import ResumeRepository
from app.services.interview_service import InterviewRoomService
from app.services.interview_finalization_service import InterviewFinalizationService


class AdminService:
    def __init__(
        self,
        interview_repo: Annotated[InterviewRepository, Depends(InterviewRepository)],
        resume_repo: Annotated[ResumeRepository, Depends(ResumeRepository)],
        interview_service: Annotated[InterviewRoomService, Depends(InterviewRoomService)],
        finalization_service: Annotated[InterviewFinalizationService, Depends(InterviewFinalizationService)]
    ):
        self.interview_repo = interview_repo
        self.resume_repo = resume_repo
        self.interview_service = interview_service
        self.finalization_service = finalization_service

    async def get_active_interview_processes(self):
        """Получить список активных AI процессов"""
        active_sessions = await self.interview_service.get_active_agent_processes()
        
        import psutil
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
            
            if session.ai_agent_pid:
                try:
                    process = psutil.Process(session.ai_agent_pid)
                    if process.is_running():
                        process_info["is_running"] = True
                        process_info["memory_mb"] = round(process.memory_info().rss / 1024 / 1024, 1)
                        process_info["cpu_percent"] = round(process.cpu_percent(interval=0.1), 1)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
                    
            processes_info.append(process_info)
        
        return {
            "active_processes": len([p for p in processes_info if p["is_running"]]),
            "total_sessions": len(processes_info),
            "processes": processes_info
        }

    async def stop_interview_process(self, session_id: int):
        """Остановить AI процесс интервью"""
        success = await self.interview_service.stop_agent_process(session_id)
        
        return {
            "success": success,
            "message": f"Process for session {session_id} {'stopped' if success else 'failed to stop'}"
        }

    async def cleanup_dead_processes(self):
        """Очистить информацию о мертвых процессах"""
        cleaned_count = await self.finalization_service.cleanup_dead_processes()
        
        return {
            "cleaned_processes": cleaned_count,
            "message": f"Cleaned up {cleaned_count} dead processes"
        }

    async def get_analytics_dashboard(self) -> Dict:
        """Основная аналитическая панель"""
        
        all_resumes = await self.resume_repo.get_all()
        
        status_stats = {}
        for resume in all_resumes:
            status = resume.status.value if hasattr(resume.status, 'value') else str(resume.status)
            status_stats[status] = status_stats.get(status, 0) + 1
        
        analyzed_count = 0
        recommendation_stats = {"strongly_recommend": 0, "recommend": 0, "consider": 0, "reject": 0}
        
        for resume in all_resumes:
            if resume.notes and "ОЦЕНКА КАНДИДАТА" in resume.notes:
                analyzed_count += 1
                notes = resume.notes.lower()
                
                if "strongly_recommend" in notes:
                    recommendation_stats["strongly_recommend"] += 1
                elif "recommend" in notes and "strongly_recommend" not in notes:
                    recommendation_stats["recommend"] += 1
                elif "consider" in notes:
                    recommendation_stats["consider"] += 1
                elif "reject" in notes:
                    recommendation_stats["reject"] += 1
        
        recent_resumes = sorted(all_resumes, key=lambda x: x.updated_at, reverse=True)[:10]
        recent_activity = []
        
        for resume in recent_resumes:
            activity_item = {
                "resume_id": resume.id,
                "candidate_name": resume.applicant_name,
                "status": resume.status.value if hasattr(resume.status, 'value') else str(resume.status),
                "updated_at": resume.updated_at.isoformat() if resume.updated_at else None,
                "has_analysis": resume.notes and "ОЦЕНКА КАНДИДАТА" in resume.notes
            }
            recent_activity.append(activity_item)
        
        return {
            "summary": {
                "total_candidates": len(all_resumes),
                "interviewed_candidates": status_stats.get("interviewed", 0),
                "analyzed_candidates": analyzed_count,
                "analysis_completion_rate": round((analyzed_count / max(len(all_resumes), 1)) * 100, 1)
            },
            "status_distribution": status_stats,
            "recommendation_distribution": recommendation_stats,
            "recent_activity": recent_activity
        }

    async def get_vacancy_analytics(self, vacancy_id: int) -> Dict:
        """Аналитика кандидатов по конкретной вакансии"""
        
        vacancy_resumes = await self.resume_repo.get_by_vacancy_id(vacancy_id)
        
        if not vacancy_resumes:
            return {
                "vacancy_id": vacancy_id,
                "message": "No candidates found for this vacancy",
                "candidates": []
            }
        
        candidates_info = []
        
        for resume in vacancy_resumes:
            overall_score = None
            recommendation = None
            
            if resume.notes and "ОЦЕНКА КАНДИДАТА" in resume.notes:
                notes = resume.notes
                if "Общий балл:" in notes:
                    try:
                        score_line = [line for line in notes.split('\n') if "Общий балл:" in line][0]
                        overall_score = int(score_line.split("Общий балл:")[1].split("/")[0].strip())
                    except:
                        pass
                
                if "Рекомендация:" in notes:
                    try:
                        rec_line = [line for line in notes.split('\n') if "Рекомендация:" in line][0]
                        recommendation = rec_line.split("Рекомендация:")[1].strip()
                    except:
                        pass
            
            candidate_info = {
                "resume_id": resume.id,
                "candidate_name": resume.applicant_name,
                "email": resume.applicant_email,
                "status": resume.status.value if hasattr(resume.status, 'value') else str(resume.status),
                "created_at": resume.created_at.isoformat() if resume.created_at else None,
                "updated_at": resume.updated_at.isoformat() if resume.updated_at else None,
                "has_analysis": resume.notes and "ОЦЕНКА КАНДИДАТА" in resume.notes,
                "overall_score": overall_score,
                "recommendation": recommendation,
                "has_parsed_data": bool(resume.parsed_data),
                "has_interview_plan": bool(resume.interview_plan)
            }
            
            candidates_info.append(candidate_info)
        
        candidates_info.sort(key=lambda x: (x['overall_score'] or 0, x['updated_at'] or ''), reverse=True)
        
        return {
            "vacancy_id": vacancy_id,
            "total_candidates": len(candidates_info),
            "candidates": candidates_info
        }

    async def generate_reports_for_vacancy(self, vacancy_id: int) -> Dict:
        """Запустить генерацию отчетов для всех кандидатов вакансии"""
        
        from celery_worker.interview_analysis_task import analyze_multiple_candidates
        
        vacancy_resumes = await self.resume_repo.get_by_vacancy_id(vacancy_id)
        
        interviewed_resumes = [r for r in vacancy_resumes if r.status in ["interviewed"]]
        
        if not interviewed_resumes:
            return {
                "error": "No interviewed candidates found for this vacancy",
                "vacancy_id": vacancy_id
            }
        
        resume_ids = [r.id for r in interviewed_resumes]
        
        task = analyze_multiple_candidates.delay(resume_ids)
        
        return {
            "vacancy_id": vacancy_id,
            "task_id": task.id,
            "message": f"Analysis started for {len(resume_ids)} candidates",
            "resume_ids": resume_ids
        }

    async def get_system_stats(self) -> Dict:
        """Общая статистика системы"""
        import psutil
        
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
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
            return {
                "error": f"Error getting system stats: {str(e)}"
            }