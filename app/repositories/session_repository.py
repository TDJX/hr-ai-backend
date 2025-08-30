from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.session import Session
from app.repositories.base_repository import BaseRepository
from datetime import datetime


class SessionRepository(BaseRepository[Session]):
    def __init__(self, session: AsyncSession):
        super().__init__(Session, session)

    async def get_by_session_id(self, session_id: str) -> Optional[Session]:
        """Get session by session_id"""
        statement = select(Session).where(
            Session.session_id == session_id,
            Session.is_active == True,
            Session.expires_at > datetime.utcnow()
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def create_session(self, user_agent: Optional[str] = None, ip_address: Optional[str] = None) -> Session:
        """Create a new session"""
        new_session = Session.create_new_session(user_agent=user_agent, ip_address=ip_address)
        return await self.create(new_session)

    async def deactivate_session(self, session_id: str) -> bool:
        """Deactivate session by session_id"""
        session = await self.get_by_session_id(session_id)
        if session:
            session.is_active = False
            session.updated_at = datetime.utcnow()
            self.session.add(session)
            await self.session.commit()
            await self.session.refresh(session)
            return True
        return False

    async def update_last_activity(self, session_id: str) -> bool:
        """Update last activity timestamp for session"""
        session = await self.get_by_session_id(session_id)
        if session:
            session.last_activity = datetime.utcnow()
            session.updated_at = datetime.utcnow()
            self.session.add(session)
            await self.session.commit()
            await self.session.refresh(session)
            return True
        return False

    async def cleanup_expired_sessions(self) -> int:
        """Remove expired sessions"""
        statement = select(Session).where(Session.expires_at < datetime.utcnow())
        result = await self.session.execute(statement)
        expired_sessions = result.scalars().all()
        
        count = 0
        for session in expired_sessions:
            await self.session.delete(session)
            count += 1
            
        await self.session.commit()
        return count