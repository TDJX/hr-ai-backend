import logging
from datetime import datetime
from typing import Annotated

from fastapi import Depends

from app.models.resume import ResumeStatus
from app.repositories.interview_repository import InterviewRepository
from app.repositories.resume_repository import ResumeRepository

logger = logging.getLogger("interview-finalization")


class InterviewFinalizationService:
    """Сервис для завершения интервью и запуска анализа"""

    def __init__(
        self,
        interview_repo: Annotated[InterviewRepository, Depends(InterviewRepository)],
        resume_repo: Annotated[ResumeRepository, Depends(ResumeRepository)],
    ):
        self.interview_repo = interview_repo
        self.resume_repo = resume_repo

    async def finalize_interview(
        self, room_name: str, dialogue_history: list, interview_metrics: dict = None
    ) -> dict | None:
        """
        Завершает интервью и запускает анализ

        Args:
            room_name: Имя комнаты LiveKit
            dialogue_history: История диалога
            interview_metrics: Метрики интервью (количество вопросов, время и т.д.)

        Returns:
            dict с информацией о завершенном интервью или None если ошибка
        """
        try:
            logger.info(f"[FINALIZE] Starting finalization for room: {room_name}")

            # 1. Находим сессию интервью
            interview_session = await self.interview_repo.get_by_room_name(room_name)
            if not interview_session:
                logger.error(
                    f"[FINALIZE] Interview session not found for room: {room_name}"
                )
                return None

            # 2. Обновляем статус сессии интервью на "completed"
            success = await self.interview_repo.update_status(
                interview_session.id, "completed", datetime.utcnow()
            )

            if not success:
                logger.error(
                    f"[FINALIZE] Failed to update session status for {interview_session.id}"
                )
                return None

            resume_id = interview_session.resume_id
            logger.info(
                f"[FINALIZE] Interview session {interview_session.id} marked as completed"
            )

            # 3. Обновляем статус резюме на "INTERVIEWED"
            resume = await self.resume_repo.get(resume_id)
            if resume:
                await self.resume_repo.update(
                    resume_id,
                    {
                        "status": ResumeStatus.INTERVIEWED,
                        "updated_at": datetime.utcnow(),
                    },
                )
                logger.info(
                    f"[FINALIZE] Resume {resume_id} status updated to INTERVIEWED"
                )
            else:
                logger.warning(f"[FINALIZE] Resume {resume_id} not found")

            # 4. Сохраняем финальную историю диалога
            await self.interview_repo.update_dialogue_history(
                room_name, dialogue_history
            )
            logger.info(
                f"[FINALIZE] Saved final dialogue ({len(dialogue_history)} messages)"
            )

            # 5. Обновляем статус AI агента
            await self.interview_repo.update_ai_agent_status(
                interview_session.id, None, "stopped"
            )

            # 6. Запускаем анализ интервью через Celery
            analysis_task = await self._start_interview_analysis(resume_id)

            # 7. Собираем итоговые метрики
            finalization_result = {
                "session_id": interview_session.id,
                "resume_id": resume_id,
                "room_name": room_name,
                "total_messages": len(dialogue_history),
                "analysis_task_id": analysis_task.get("task_id")
                if analysis_task
                else None,
                "completed_at": datetime.utcnow().isoformat(),
                "metrics": interview_metrics or {},
            }

            logger.info(
                f"[FINALIZE] Interview successfully finalized: {finalization_result}"
            )
            return finalization_result

        except Exception as e:
            logger.error(
                f"[FINALIZE] Error finalizing interview for room {room_name}: {str(e)}"
            )
            return None

    async def _start_interview_analysis(self, resume_id: int):
        """Запускает анализ интервью через Celery"""
        # try:
        logger.info(
            f"[FINALIZE] Attempting to start analysis task for resume_id: {resume_id}"
        )

        # Импортируем задачу
        #     from celery_worker.interview_analysis_task import generate_interview_report
        #     logger.debug(f"[FINALIZE] Successfully imported generate_interview_report task")
        #
        #     # Запускаем задачу
        #     task = generate_interview_report.delay(resume_id)
        #     logger.info(f"[FINALIZE] Analysis task started: {task.id} for resume_id: {resume_id}")
        #     return task
        #
        # except ImportError as e:
        #     logger.error(f"[FINALIZE] Import error for analysis task: {str(e)}")
        #     return None
        # except ConnectionError as e:
        #     logger.error(f"[FINALIZE] Connection error starting analysis task for resume {resume_id}: {str(e)}")
        #     logger.warning(f"[FINALIZE] This may indicate Redis/Celery broker is not accessible from AI agent process")
        #
        #     # Fallback: попытка запуска анализа через HTTP API
        #     return await self._start_analysis_via_http(resume_id)
        # except Exception as e:
        #     logger.error(f"[FINALIZE] Failed to start analysis task for resume {resume_id}: {str(e)}")
        #     logger.debug(f"[FINALIZE] Exception type: {type(e).__name__}")

        # Fallback: попытка запуска анализа через HTTP API для любых других ошибок
        return await self._start_analysis_via_http(resume_id)

    async def _start_analysis_via_http(self, resume_id: int):
        """Fallback: запуск анализа через HTTP API (когда Celery недоступен из AI агента)"""
        try:
            import httpx

            url = f"http://localhost:8000/api/v1/analysis/interview-report/{resume_id}"
            logger.info(f"[FINALIZE] Attempting HTTP fallback to URL: {url}")

            # Попробуем отправить HTTP запрос на локальный API для запуска анализа
            async with httpx.AsyncClient() as client:
                response = await client.post(url, timeout=5.0)

                if response.status_code == 200:
                    result = response.json()
                    logger.info(
                        f"[FINALIZE] Analysis started via HTTP API for resume_id: {resume_id}, task_id: {result.get('task_id', 'unknown')}"
                    )
                    return result
                else:
                    logger.error(
                        f"[FINALIZE] HTTP API returned {response.status_code} for resume_id: {resume_id}"
                    )
                    logger.debug(f"[FINALIZE] Response body: {response.text[:200]}")
                    return None

        except Exception as e:
            logger.error(
                f"[FINALIZE] HTTP fallback failed for resume {resume_id}: {str(e)}"
            )
            return None

    async def save_dialogue_to_session(
        self, room_name: str, dialogue_history: list
    ) -> bool:
        """Сохраняет диалог в сессию (для промежуточных сохранений)"""
        try:
            success = await self.interview_repo.update_dialogue_history(
                room_name, dialogue_history
            )
            if success:
                logger.info(
                    f"[DIALOGUE] Saved {len(dialogue_history)} messages for room: {room_name}"
                )
            return success
        except Exception as e:
            logger.error(
                f"[DIALOGUE] Error saving dialogue for room {room_name}: {str(e)}"
            )
            return False

    async def cleanup_dead_processes(self) -> int:
        """Очищает информацию о мертвых AI процессах"""
        try:
            import psutil

            active_sessions = (
                await self.interview_repo.get_sessions_with_running_agents()
            )
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

            logger.info(f"[CLEANUP] Cleaned up {cleaned_count} dead processes")
            return cleaned_count

        except Exception as e:
            logger.error(f"[CLEANUP] Error cleaning up processes: {str(e)}")
            return 0
