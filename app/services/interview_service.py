import time
import uuid
from typing import Annotated

from fastapi import Depends
from livekit.api import AccessToken, VideoGrants

from app.models.interview import (
    InterviewSession,
    InterviewValidationResponse,
    LiveKitTokenResponse,
)
from app.models.resume import ResumeStatus
from app.repositories.interview_repository import InterviewRepository
from app.repositories.resume_repository import ResumeRepository
from app.repositories.vacancy_repository import VacancyRepository
from app.services.agent_manager import agent_manager
from rag.settings import settings


class InterviewRoomService:
    def __init__(
        self,
        interview_repo: Annotated[InterviewRepository, Depends(InterviewRepository)],
        resume_repo: Annotated[ResumeRepository, Depends(ResumeRepository)],
        vacancy_repo: Annotated[VacancyRepository, Depends(VacancyRepository)],
    ):
        self.interview_repo = interview_repo
        self.resume_repo = resume_repo
        self.vacancy_repo = vacancy_repo
        self.livekit_url = settings.livekit_url or "ws://localhost:7880"
        self.api_key = settings.livekit_api_key or "devkey"
        self.api_secret = settings.livekit_api_secret or "secret"

    async def validate_resume_for_interview(
        self, resume_id: int
    ) -> InterviewValidationResponse:
        """Проверяет, можно ли проводить собеседование для данного резюме"""
        try:
            # Получаем резюме
            resume = await self.resume_repo.get(resume_id)

            if not resume:
                return InterviewValidationResponse(
                    can_interview=False, message="Resume not found"
                )

            # Проверяем статус резюме
            if resume.status != ResumeStatus.PARSED:
                return InterviewValidationResponse(
                    can_interview=False,
                    message=f"Resume is not ready for interview. Current status: {resume.status}",
                )

            # Проверяем активную сессию только для информации (не блокируем)
            active_session = await self.interview_repo.get_active_session_by_resume_id(
                resume_id
            )

            message = "Resume is ready for interview"
            if active_session:
                message = "Resume has an active interview session"

            return InterviewValidationResponse(can_interview=True, message=message)

        except Exception as e:
            return InterviewValidationResponse(
                can_interview=False, message=f"Error validating resume: {str(e)}"
            )

    async def create_interview_session(self, resume_id: int) -> InterviewSession | None:
        """Создает новую сессию собеседования"""
        try:
            # Генерируем уникальное имя комнаты с UUID
            unique_id = str(uuid.uuid4())[:8]
            timestamp = int(time.time())
            room_name = f"interview_{resume_id}_{timestamp}_{unique_id}"

            # Создаем сессию в БД через репозиторий
            interview_session = await self.interview_repo.create_interview_session(
                resume_id, room_name
            )

            return interview_session

        except Exception as e:
            print(f"Error creating interview session: {str(e)}")
            return None

    def generate_access_token(self, room_name: str, participant_name: str) -> str:
        """Генерирует JWT токен для LiveKit"""
        try:
            at = AccessToken(self.api_key, self.api_secret)
            # Исправляем использование grants
            grants = VideoGrants(
                room_join=True, room=room_name, can_publish=True, can_subscribe=True
            )
            at.with_grants(grants).with_identity(participant_name)

            return at.to_jwt()

        except Exception as e:
            print(f"Error generating LiveKit token: {str(e)}")
            raise

    async def get_livekit_token(self, resume_id: int) -> LiveKitTokenResponse | None:
        """Создает сессию собеседования и возвращает токен для LiveKit"""
        try:
            # Валидируем резюме
            validation = await self.validate_resume_for_interview(resume_id)
            if not validation.can_interview:
                return None

            # Проверяем, есть ли уже созданная сессия для этого резюме
            existing_session = (
                await self.interview_repo.get_active_session_by_resume_id(resume_id)
            )
            if existing_session:
                # Используем существующую сессию
                interview_session = existing_session
                print(
                    f"[DEBUG] Using existing interview session: {interview_session.id}"
                )
            else:
                # Проверяем доступность агента
                if not agent_manager.is_available():
                    print("[ERROR] AI Agent is not available for new interview")
                    return None

                # Создаем новую сессию собеседования
                interview_session = await self.create_interview_session(resume_id)
                if not interview_session:
                    return None
                print(f"[DEBUG] Created new interview session: {interview_session.id}")

                # Получаем готовый план интервью для AI агента
                interview_plan = await self.get_resume_data_for_interview(resume_id)

                # Получаем данные вакансии
                resume = await self.resume_repo.get(resume_id)
                vacancy_data = None
                if resume and resume.vacancy_id:
                    vacancy = await self.vacancy_repo.get_by_id(resume.vacancy_id)
                    if vacancy:
                        # Конвертируем объект вакансии в словарь для JSON сериализации
                        vacancy_data = {
                            "title": vacancy.title,
                            "description": vacancy.description,
                            "key_skills": vacancy.key_skills,
                            "employment_type": vacancy.employment_type,
                            "experience": vacancy.experience,
                            "schedule": vacancy.schedule,
                            "area_name": vacancy.area_name,
                            "professional_roles": vacancy.professional_roles,
                            "contacts_name": vacancy.contacts_name,
                        }

                # Обновляем статус сессии на ACTIVE
                await self.interview_repo.update_session_status(
                    interview_session.id, "active"
                )

                # Назначаем сессию агенту через менеджер
                success = await agent_manager.assign_session(
                    interview_session.id,
                    interview_session.room_name,
                    interview_plan,
                    vacancy_data,
                )

                if not success:
                    print("[ERROR] Failed to assign session to AI agent")
                    return None

            # Генерируем токен
            participant_name = f"user_{resume_id}"
            token = self.generate_access_token(
                interview_session.room_name, participant_name
            )

            return LiveKitTokenResponse(
                token=token,
                room_name=interview_session.room_name,
                server_url=self.livekit_url,
                session_id=interview_session.id,
            )

        except Exception as e:
            print(f"Error getting LiveKit token: {str(e)}")
            return None

    async def update_session_status(self, session_id: int, status: str) -> bool:
        """Обновляет статус сессии собеседования"""
        return await self.interview_repo.update_session_status(session_id, status)

    async def get_interview_session(self, resume_id: int) -> InterviewSession | None:
        """Получает активную сессию собеседования для резюме"""
        return await self.interview_repo.get_active_session_by_resume_id(resume_id)

    async def end_interview_session(self, session_id: int) -> bool:
        """Завершает интервью-сессию и освобождает агента"""
        try:
            # Освобождаем агента от текущей сессии
            await agent_manager.release_session()

            # Обновляем статус сессии
            await self.interview_repo.update_session_status(session_id, "completed")

            print(f"[DEBUG] Interview session {session_id} ended successfully")
            return True

        except Exception as e:
            print(f"Error ending interview session {session_id}: {str(e)}")
            return False

    def get_agent_status(self) -> dict:
        """Получает текущий статус AI агента"""
        return agent_manager.get_status()

    async def get_resume_data_for_interview(self, resume_id: int) -> dict:
        """Получает готовый план интервью из базы данных"""
        try:
            # Получаем резюме с готовым планом интервью
            resume = await self.resume_repo.get(resume_id)

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
                            "questions": [
                                "Расскажи немного о себе",
                                "Что тебя привлекло в этой позиции?",
                            ],
                        },
                        {
                            "name": "Опыт работы",
                            "duration_minutes": 15,
                            "questions": [
                                "Расскажи о своем опыте",
                                "Какие технологии используешь?",
                            ],
                        },
                        {
                            "name": "Вопросы кандидата",
                            "duration_minutes": 10,
                            "questions": ["Есть ли у тебя вопросы ко мне?"],
                        },
                    ],
                },
                "focus_areas": ["experience", "technical_skills"],
                "candidate_info": {
                    "name": resume.applicant_name,
                    "email": resume.applicant_email,
                    "phone": resume.applicant_phone,
                },
            }

            # Добавляем parsed данные если есть
            if resume.parsed_data:
                fallback_plan["candidate_info"].update(
                    {
                        "skills": resume.parsed_data.get("skills", []),
                        "total_years": resume.parsed_data.get("total_years", 0),
                        "education": resume.parsed_data.get("education", ""),
                    }
                )

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
                        "questions": [
                            "Расскажи о себе",
                            "Что тебя привлекло в этой позиции?",
                        ],
                    },
                    {
                        "name": "Опыт работы",
                        "duration_minutes": 15,
                        "questions": [
                            "Расскажи о своем опыте",
                            "Какие технологии используешь?",
                        ],
                    },
                    {
                        "name": "Вопросы кандидата",
                        "duration_minutes": 5,
                        "questions": ["Есть ли у тебя вопросы?"],
                    },
                ],
            },
            "focus_areas": ["experience", "technical_skills"],
            "candidate_info": {"name": "Кандидат", "skills": [], "total_years": 0},
        }

    async def update_agent_process_info(
        self, session_id: int, pid: int = None, status: str = "not_started"
    ) -> bool:
        """Обновляет информацию о процессе AI агента"""
        return await self.interview_repo.update_ai_agent_status(session_id, pid, status)

    async def get_active_agent_processes(self) -> list:
        """Получает список активных AI процессов"""
        return await self.interview_repo.get_sessions_with_running_agents()

    async def stop_agent_process(self, session_id: int) -> bool:
        """Останавливает AI процесс для сессии"""
        try:
            session = await self.interview_repo.get(session_id)

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
                await self.interview_repo.update_ai_agent_status(
                    session_id, None, "stopped"
                )

                print(
                    f"Stopped AI agent process {session.ai_agent_pid} for session {session_id}"
                )
                return True

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # Процесс уже не существует
                await self.interview_repo.update_ai_agent_status(
                    session_id, None, "stopped"
                )
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
                            await self.interview_repo.update_ai_agent_status(
                                session.id, None, "stopped"
                            )
                            cleaned_count += 1
                    except psutil.NoSuchProcess:
                        await self.interview_repo.update_ai_agent_status(
                            session.id, None, "stopped"
                        )
                        cleaned_count += 1

            print(f"Cleaned up {cleaned_count} dead processes")
            return cleaned_count

        except Exception as e:
            print(f"Error cleaning up processes: {str(e)}")
            return 0
