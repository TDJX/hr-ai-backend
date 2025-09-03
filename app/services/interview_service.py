import os
import time
import uuid
import json
import subprocess
from typing import Optional
from datetime import datetime, timedelta
from livekit.api import AccessToken, VideoGrants
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.interview import (
    InterviewSession, 
    InterviewSessionCreate, 
    InterviewSessionUpdate,
    InterviewStatus,
    InterviewValidationResponse,
    LiveKitTokenResponse
)
from app.models.resume import Resume, ResumeStatus
from app.models.vacancy import Vacancy
from rag.settings import settings


class InterviewRoomService:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.livekit_url = settings.livekit_url or "ws://localhost:7880"
        self.api_key = settings.livekit_api_key or "devkey"
        self.api_secret = settings.livekit_api_secret or "secret"
        
    async def validate_resume_for_interview(self, resume_id: int) -> InterviewValidationResponse:
        """Проверяет, можно ли проводить собеседование для данного резюме"""
        try:
            # Получаем резюме
            result = await self.db.execute(select(Resume).where(Resume.id == resume_id))
            resume = result.scalar_one_or_none()
            
            if not resume:
                return InterviewValidationResponse(
                    can_interview=False,
                    message="Resume not found"
                )
            
            # Проверяем статус резюме
            if resume.status != ResumeStatus.PARSED:
                return InterviewValidationResponse(
                    can_interview=False,
                    message=f"Resume is not ready for interview. Current status: {resume.status}"
                )
            
            # Проверяем активную сессию только для информации (не блокируем)
            result = await self.db.execute(
                select(InterviewSession)
                .where(InterviewSession.resume_id == resume_id)
                .where(InterviewSession.status == "active")
            )
            active_session = result.scalar_one_or_none()
            
            message = "Resume is ready for interview"
            if active_session:
                message = "Resume has an active interview session"
            
            return InterviewValidationResponse(
                can_interview=True,
                message=message
            )
            
        except Exception as e:
            return InterviewValidationResponse(
                can_interview=False,
                message=f"Error validating resume: {str(e)}"
            )
    
    async def create_interview_session(self, resume_id: int) -> Optional[InterviewSession]:
        """Создает новую сессию собеседования"""
        try:
            # Генерируем уникальное имя комнаты с UUID
            unique_id = str(uuid.uuid4())[:8]
            timestamp = int(time.time())
            room_name = f"interview_{resume_id}_{timestamp}_{unique_id}"
            
            # Создаем сессию в БД
            session_data = InterviewSessionCreate(
                resume_id=resume_id,
                room_name=room_name
            )
            
            interview_session = InterviewSession(**session_data.model_dump())
            self.db.add(interview_session)
            await self.db.commit()
            await self.db.refresh(interview_session)
            
            return interview_session
            
        except Exception as e:
            await self.db.rollback()
            print(f"Error creating interview session: {str(e)}")
            return None
    
    def generate_access_token(self, room_name: str, participant_name: str) -> str:
        """Генерирует JWT токен для LiveKit"""
        try:
            at = AccessToken(self.api_key, self.api_secret)
            # Исправляем использование grants
            grants = VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True
            )
            at.with_grants(grants).with_identity(participant_name)
            
            return at.to_jwt()
            
        except Exception as e:
            print(f"Error generating LiveKit token: {str(e)}")
            raise
    
    async def get_livekit_token(self, resume_id: int) -> Optional[LiveKitTokenResponse]:
        """Создает сессию собеседования и возвращает токен для LiveKit"""
        try:
            # Валидируем резюме
            validation = await self.validate_resume_for_interview(resume_id)
            if not validation.can_interview:
                return None
            
            # Проверяем, есть ли уже созданная сессия для этого резюме
            existing_session = await self.get_interview_session(resume_id)
            if existing_session:
                # Используем существующую сессию
                interview_session = existing_session
                print(f"[DEBUG] Using existing interview session: {interview_session.id}")
            else:
                # Создаем новую сессию собеседования
                interview_session = await self.create_interview_session(resume_id)
                if not interview_session:
                    return None
                print(f"[DEBUG] Created new interview session: {interview_session.id}")
            
            # Генерируем токен
            participant_name = f"user_{resume_id}"
            token = self.generate_access_token(
                interview_session.room_name, 
                participant_name
            )
            
            # Получаем готовый план интервью для AI агента
            interview_plan = await self.get_resume_data_for_interview(resume_id)
            
            # Обновляем статус сессии на ACTIVE
            await self.update_session_status(interview_session.id, "active")
            
            # Запускаем AI агента для этой сессии
            await self.start_ai_interviewer(interview_session, interview_plan)
            
            return LiveKitTokenResponse(
                token=token,
                room_name=interview_session.room_name,
                server_url=self.livekit_url
            )
            
        except Exception as e:
            print(f"Error getting LiveKit token: {str(e)}")
            return None
    
    async def update_session_status(self, session_id: int, status: str) -> bool:
        """Обновляет статус сессии собеседования"""
        try:
            result = await self.db.execute(
                select(InterviewSession).where(InterviewSession.id == session_id)
            )
            session = result.scalar_one_or_none()
            
            if not session:
                return False
            
            session.status = status
            if status == "completed":
                session.completed_at = datetime.utcnow()
            
            await self.db.commit()
            return True
            
        except Exception as e:
            await self.db.rollback()
            print(f"Error updating session status: {str(e)}")
            return False
    
    async def get_interview_session(self, resume_id: int) -> Optional[InterviewSession]:
        """Получает активную сессию собеседования для резюме"""
        try:
            result = await self.db.execute(
                select(InterviewSession)
                .where(InterviewSession.resume_id == resume_id)
                .where(InterviewSession.status.in_(["created", "active"]))
                .order_by(InterviewSession.started_at.desc())
            )
            return result.scalar_one_or_none()
            
        except Exception as e:
            print(f"Error getting interview session: {str(e)}")
            return None
    
    async def start_ai_interviewer(self, interview_session: InterviewSession, interview_plan: dict):
        """Запускает AI интервьюера для сессии"""
        try:
            # Создаем токен для AI агента
            ai_token = self.generate_access_token(
                interview_session.room_name, 
                f"ai_interviewer_{interview_session.id}"
            )
            
            # Подготавливаем метаданные с планом интервью
            room_metadata = json.dumps({
                "interview_plan": interview_plan,
                "session_id": interview_session.id
            })
            
            # Запускаем AI агента в отдельном процессе
            agent_cmd = [
                "uv",
                "run",
                "ai_interviewer_agent.py",
                "connect",
                "--room", interview_session.room_name,
                "--url", self.livekit_url,
                "--api-key", self.api_key,
                "--api-secret", self.api_secret,
            ]
            
            # Устанавливаем переменные окружения
            env = os.environ.copy()
            env.update({
                "LIVEKIT_ROOM_METADATA": room_metadata,
                "OPENAI_API_KEY": settings.openai_api_key or "",
                "DEEPGRAM_API_KEY": settings.deepgram_api_key or "",
                "CARTESIA_API_KEY": settings.cartesia_api_key or "",
            })
            
            # Запускаем процесс в фоне
            with open(f"ai_interviewer_{interview_session.id}.log", "wb") as f_out, \
                    open(f"ai_interviewer_{interview_session.id}.err", "wb") as f_err:
                process = subprocess.Popen(
                    agent_cmd,
                    env=env,
                    stdout=f_out,
                    stderr=f_err,
                    cwd="."
                )
            
            print(f"[DEBUG] Started AI interviewer process {process.pid} for session {interview_session.id}")
            
            # Сохраняем PID процесса в БД для управления
            await self.update_agent_process_info(
                interview_session.id, 
                process.pid, 
                "running"
            )
            
        except Exception as e:
            print(f"Error starting AI interviewer: {str(e)}")
            # Обновляем статус на failed
            await self.update_agent_process_info(
                interview_session.id, 
                None, 
                "failed"
            )
    
    async def get_resume_data_for_interview(self, resume_id: int) -> dict:
        """Получает готовый план интервью из базы данных"""
        try:
            # Получаем резюме с готовым планом интервью
            result = await self.db.execute(
                select(Resume).where(Resume.id == resume_id)
            )
            resume = result.scalar_one_or_none()
            
            if not resume:
                return self._get_fallback_interview_plan()
            
            # Если есть готовый план интервью - используем его
            if resume.interview_plan:
                return resume.interview_plan
            
            # Если плана нет, создаем базовый план на основе имеющихся данных
            fallback_plan = {
                "interview_structure": {
                    "duration_minutes": 30,
                    "greeting": f"Привет, {resume.applicant_name}! Готов к интервью?",
                    "sections": [
                        {
                            "name": "Знакомство",
                            "duration_minutes": 5,
                            "questions": ["Расскажи немного о себе", "Что тебя привлекло в этой позиции?"]
                        },
                        {
                            "name": "Опыт работы",
                            "duration_minutes": 15,
                            "questions": ["Расскажи о своем опыте", "Какие технологии используешь?"]
                        },
                        {
                            "name": "Вопросы кандидата",
                            "duration_minutes": 10,
                            "questions": ["Есть ли у тебя вопросы ко мне?"]
                        }
                    ]
                },
                "focus_areas": ["experience", "technical_skills"],
                "candidate_info": {
                    "name": resume.applicant_name,
                    "email": resume.applicant_email,
                    "phone": resume.applicant_phone
                }
            }
            
            # Добавляем parsed данные если есть
            if resume.parsed_data:
                fallback_plan["candidate_info"].update({
                    "skills": resume.parsed_data.get("skills", []),
                    "total_years": resume.parsed_data.get("total_years", 0),
                    "education": resume.parsed_data.get("education", "")
                })
            
            return fallback_plan
            
        except Exception as e:
            print(f"Error getting interview plan: {str(e)}")
            return self._get_fallback_interview_plan()
    
    def _get_fallback_interview_plan(self) -> dict:
        """Fallback план интервью если не удалось загрузить из БД"""
        return {
            "interview_structure": {
                "duration_minutes": 30,
                "greeting": "Привет! Готов к интервью?",
                "sections": [
                    {
                        "name": "Знакомство",
                        "duration_minutes": 10,
                        "questions": ["Расскажи о себе", "Что тебя привлекло в этой позиции?"]
                    },
                    {
                        "name": "Опыт работы",
                        "duration_minutes": 15,
                        "questions": ["Расскажи о своем опыте", "Какие технологии используешь?"]
                    },
                    {
                        "name": "Вопросы кандидата",
                        "duration_minutes": 5,
                        "questions": ["Есть ли у тебя вопросы?"]
                    }
                ]
            },
            "focus_areas": ["experience", "technical_skills"],
            "candidate_info": {
                "name": "Кандидат",
                "skills": [],
                "total_years": 0
            }
        }
    
    async def update_agent_process_info(self, session_id: int, pid: int = None, status: str = "not_started") -> bool:
        """Обновляет информацию о процессе AI агента"""
        try:
            result = await self.db.execute(
                select(InterviewSession).where(InterviewSession.id == session_id)
            )
            session = result.scalar_one_or_none()
            
            if not session:
                return False
            
            session.ai_agent_pid = pid
            session.ai_agent_status = status
            
            await self.db.commit()
            return True
            
        except Exception as e:
            await self.db.rollback()
            print(f"Error updating agent process info: {str(e)}")
            return False
    
    async def get_active_agent_processes(self) -> list:
        """Получает список активных AI процессов"""
        try:
            result = await self.db.execute(
                select(InterviewSession)
                .where(InterviewSession.ai_agent_status == "running")
            )
            return result.scalars().all()
            
        except Exception as e:
            print(f"Error getting active processes: {str(e)}")
            return []
    
    async def stop_agent_process(self, session_id: int) -> bool:
        """Останавливает AI процесс для сессии"""
        try:
            result = await self.db.execute(
                select(InterviewSession).where(InterviewSession.id == session_id)
            )
            session = result.scalar_one_or_none()
            
            if not session or not session.ai_agent_pid:
                return False
            
            import psutil
            try:
                # Пытаемся gracefully остановить процесс
                process = psutil.Process(session.ai_agent_pid)
                process.terminate()
                
                # Ждем завершения до 5 секунд
                import time
                for _ in range(50):
                    if not process.is_running():
                        break
                    time.sleep(0.1)
                
                # Если не завершился, принудительно убиваем
                if process.is_running():
                    process.kill()
                
                # Обновляем статус в БД
                await self.update_agent_process_info(session_id, None, "stopped")
                
                print(f"Stopped AI agent process {session.ai_agent_pid} for session {session_id}")
                return True
                
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # Процесс уже не существует
                await self.update_agent_process_info(session_id, None, "stopped")
                return True
                
        except Exception as e:
            print(f"Error stopping agent process: {str(e)}")
            return False
    
    async def cleanup_dead_processes(self) -> int:
        """Очищает информацию о мертвых процессах"""
        try:
            import psutil
            
            active_sessions = await self.get_active_agent_processes()
            cleaned_count = 0
            
            for session in active_sessions:
                if session.ai_agent_pid:
                    try:
                        process = psutil.Process(session.ai_agent_pid)
                        if not process.is_running():
                            await self.update_agent_process_info(session.id, None, "stopped")
                            cleaned_count += 1
                    except psutil.NoSuchProcess:
                        await self.update_agent_process_info(session.id, None, "stopped")
                        cleaned_count += 1
            
            print(f"Cleaned up {cleaned_count} dead processes")
            return cleaned_count
            
        except Exception as e:
            print(f"Error cleaning up processes: {str(e)}")
            return 0
    
    async def get_resume_with_interview_plan(self, resume_id: int) -> Optional[Resume]:
        """Получает резюме с планом интервью"""
        try:
            result = await self.db.execute(select(Resume).where(Resume.id == resume_id))
            return result.scalar_one_or_none()
        except Exception as e:
            print(f"Error getting resume with interview plan: {str(e)}")
            return None
    
    async def create_interview_session(self, resume_id: int) -> Optional[InterviewSession]:
        """Создает новую сессию интервью"""
        try:
            # Генерируем уникальное имя комнаты
            room_name = f"interview_{resume_id}_{int(time.time())}"
            
            new_session = InterviewSession(
                resume_id=resume_id,
                room_name=room_name,
                status="created"
            )
            
            self.db.add(new_session)
            await self.db.commit()
            await self.db.refresh(new_session)
            
            return new_session
            
        except Exception as e:
            await self.db.rollback()
            print(f"Error creating interview session: {str(e)}")
            return None
    
    async def delete_interview_session(self, session_id: int) -> bool:
        """Удаляет сессию интервью"""
        try:
            result = await self.db.execute(
                select(InterviewSession).where(InterviewSession.id == session_id)
            )
            session = result.scalar_one_or_none()
            
            if not session:
                return False
            
            await self.db.delete(session)
            await self.db.commit()
            return True
            
        except Exception as e:
            await self.db.rollback()
            print(f"Error deleting interview session: {str(e)}")
            return False
