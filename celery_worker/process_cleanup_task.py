import asyncio
from celery import current_task
from celery_worker.celery_app import celery_app
from celery_worker.database import get_sync_session
from app.services.interview_service import InterviewRoomService
import psutil


@celery_app.task(bind=True)
def cleanup_interview_processes_task(self):
    """
    Периодическая задача очистки мертвых AI процессов
    """
    try:
        self.update_state(
            state='PROGRESS',
            meta={'status': 'Checking for dead AI processes...', 'progress': 10}
        )
        
        # Используем синхронный подход для Celery
        with get_sync_session() as session:
            # Получаем все "активные" сессии из БД
            from app.models.interview import InterviewSession
            active_sessions = session.query(InterviewSession).filter(
                InterviewSession.ai_agent_status == "running"
            ).all()
            
            cleaned_count = 0
            total_sessions = len(active_sessions)
            
            self.update_state(
                state='PROGRESS',
                meta={'status': f'Found {total_sessions} potentially active sessions...', 'progress': 30}
            )
            
            for i, interview_session in enumerate(active_sessions):
                if interview_session.ai_agent_pid:
                    try:
                        # Проверяем, жив ли процесс
                        process = psutil.Process(interview_session.ai_agent_pid)
                        
                        if not process.is_running():
                            # Процесс мертв, обновляем статус
                            interview_session.ai_agent_pid = None
                            interview_session.ai_agent_status = "stopped"
                            session.add(interview_session)
                            cleaned_count += 1
                            
                    except psutil.NoSuchProcess:
                        # Процесс не существует
                        interview_session.ai_agent_pid = None
                        interview_session.ai_agent_status = "stopped"
                        session.add(interview_session)
                        cleaned_count += 1
                        
                    except Exception as e:
                        print(f"Error checking process {interview_session.ai_agent_pid}: {str(e)}")
                
                # Обновляем прогресс
                progress = 30 + (i + 1) / total_sessions * 60
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'status': f'Processed {i + 1}/{total_sessions} sessions...', 
                        'progress': progress
                    }
                )
            
            # Сохраняем изменения
            session.commit()
            
            self.update_state(
                state='SUCCESS',
                meta={
                    'status': f'Cleanup completed. Cleaned {cleaned_count} dead processes.',
                    'progress': 100,
                    'cleaned_count': cleaned_count,
                    'total_checked': total_sessions
                }
            )
            
            return {
                'status': 'completed',
                'cleaned_count': cleaned_count,
                'total_checked': total_sessions
            }
            
    except Exception as e:
        self.update_state(
            state='FAILURE',
            meta={
                'status': f'Error during cleanup: {str(e)}',
                'progress': 0,
                'error': str(e)
            }
        )
        raise


@celery_app.task(bind=True)
def force_kill_interview_process_task(self, session_id: int):
    """
    Принудительное завершение AI процесса для сессии
    """
    try:
        self.update_state(
            state='PROGRESS',
            meta={'status': f'Looking for session {session_id}...', 'progress': 20}
        )
        
        with get_sync_session() as session:
            from app.models.interview import InterviewSession
            
            interview_session = session.query(InterviewSession).filter(
                InterviewSession.id == session_id
            ).first()
            
            if not interview_session:
                return {
                    'status': 'not_found',
                    'message': f'Session {session_id} not found'
                }
            
            if not interview_session.ai_agent_pid:
                return {
                    'status': 'no_process',
                    'message': f'No AI process found for session {session_id}'
                }
            
            self.update_state(
                state='PROGRESS',
                meta={'status': f'Terminating process {interview_session.ai_agent_pid}...', 'progress': 50}
            )
            
            try:
                process = psutil.Process(interview_session.ai_agent_pid)
                
                # Graceful terminate
                process.terminate()
                
                # Ждем до 5 секунд
                import time
                for _ in range(50):
                    if not process.is_running():
                        break
                    time.sleep(0.1)
                
                # Если не помогло, убиваем принудительно
                if process.is_running():
                    process.kill()
                    time.sleep(0.5)  # Даем время на завершение
                
                # Обновляем статус в БД
                interview_session.ai_agent_pid = None
                interview_session.ai_agent_status = "stopped"
                session.add(interview_session)
                session.commit()
                
                self.update_state(
                    state='SUCCESS',
                    meta={'status': 'Process terminated successfully', 'progress': 100}
                )
                
                return {
                    'status': 'terminated',
                    'message': f'AI process for session {session_id} terminated successfully'
                }
                
            except psutil.NoSuchProcess:
                # Процесс уже не существует
                interview_session.ai_agent_pid = None
                interview_session.ai_agent_status = "stopped"
                session.add(interview_session)
                session.commit()
                
                return {
                    'status': 'already_dead',
                    'message': f'Process was already dead, cleaned up database'
                }
                
    except Exception as e:
        self.update_state(
            state='FAILURE',
            meta={
                'status': f'Error terminating process: {str(e)}',
                'progress': 0,
                'error': str(e)
            }
        )
        raise