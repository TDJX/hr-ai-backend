from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timedelta
import uuid


class SessionBase(SQLModel):
    session_id: str = Field(max_length=255, unique=True, index=True)
    user_agent: Optional[str] = Field(max_length=512)
    ip_address: Optional[str] = Field(max_length=45)
    is_active: bool = Field(default=True)
    expires_at: datetime = Field(default_factory=lambda: datetime.utcnow() + timedelta(days=30))
    last_activity: datetime = Field(default_factory=datetime.utcnow)


class Session(SessionBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @classmethod
    def create_new_session(cls, user_agent: Optional[str] = None, ip_address: Optional[str] = None) -> "Session":
        """Create a new session with a unique session_id"""
        return cls(
            session_id=str(uuid.uuid4()),
            user_agent=user_agent,
            ip_address=ip_address
        )

    def is_expired(self) -> bool:
        """Check if session is expired"""
        return datetime.utcnow() > self.expires_at

    def extend_session(self, days: int = 30) -> None:
        """Extend session expiration"""
        self.expires_at = datetime.utcnow() + timedelta(days=days)
        self.last_activity = datetime.utcnow()


class SessionCreate(SessionBase):
    pass


class SessionRead(SessionBase):
    id: int
    created_at: datetime
    updated_at: datetime