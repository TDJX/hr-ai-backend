from datetime import datetime
from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.interview import InterviewSession
from app.repositories.base_repository import BaseRepository


class InterviewRepository(BaseRepository[InterviewSession]):
    def __init__(self, session: Annotated[AsyncSession, Depends(get_session)]):
        super().__init__(InterviewSession, session)

    async def get_by_room_name(self, room_name: str) -> InterviewSession | None:
        """Получить сессию интервью по имени комнаты"""
        statement = select(InterviewSession).where(
            InterviewSession.room_name == room_name
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def update_status(
        self, session_id: int, status: str, completed_at: datetime | None = None
    ) -> bool:
        """Обновить статус сессии"""
        try:
            # Получаем объект и обновляем его напрямую
            result = await self._session.execute(
                select(InterviewSession).where(InterviewSession.id == session_id)
            )
            session_obj = result.scalar_one_or_none()

            if not session_obj:
                return False

            session_obj.status = status
            if completed_at:
                session_obj.completed_at = completed_at

            await self._session.commit()
            return True
        except Exception:
            await self._session.rollback()
            return False

    async def update_dialogue_history(
        self, room_name: str, dialogue_history: list
    ) -> bool:
        """Обновить историю диалога для сессии"""
        try:
            # Получаем объект и обновляем его напрямую
            result = await self._session.execute(
                select(InterviewSession).where(InterviewSession.room_name == room_name)
            )
            session_obj = result.scalar_one_or_none()

            if not session_obj:
                return False

            session_obj.dialogue_history = dialogue_history
            await self._session.commit()
            return True
        except Exception:
            await self._session.rollback()
            return False

    async def update_ai_agent_status(
        self, session_id: int, pid: int | None = None, status: str = "not_started"
    ) -> bool:
        """Обновить статус AI агента"""
        try:
            # Получаем объект и обновляем его напрямую
            result = await self._session.execute(
                select(InterviewSession).where(InterviewSession.id == session_id)
            )
            session_obj = result.scalar_one_or_none()

            if not session_obj:
                return False

            session_obj.ai_agent_pid = pid
            session_obj.ai_agent_status = status
            await self._session.commit()
            return True
        except Exception:
            await self._session.rollback()
            return False

    async def get_sessions_with_running_agents(self) -> list[InterviewSession]:
        """Получить сессии с запущенными AI агентами"""
        statement = select(InterviewSession).where(
            InterviewSession.ai_agent_status == "running"
        )
        result = await self._session.execute(statement)
        return result.scalars().all()

    async def get_active_session_by_resume_id(
        self, resume_id: int
    ) -> InterviewSession | None:
        """Получить активную сессию собеседования для резюме"""
        statement = (
            select(InterviewSession)
            .where(InterviewSession.resume_id == resume_id)
            .where(InterviewSession.status.in_(["created", "active"]))
            .order_by(InterviewSession.started_at.desc())
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def create_interview_session(
        self, resume_id: int, room_name: str
    ) -> InterviewSession:
        """Создать новую сессию интервью"""
        from app.models.interview import InterviewSessionCreate

        session_data = InterviewSessionCreate(resume_id=resume_id, room_name=room_name)
        return await self.create(session_data.model_dump())

    async def update_session_status(self, session_id: int, status: str) -> bool:
        """Обновить статус сессии (алиас для update_status)"""
        completed_at = None
        if status == "completed":
            completed_at = datetime.utcnow()
        return await self.update_status(session_id, status, completed_at)
