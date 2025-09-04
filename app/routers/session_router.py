import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.session_middleware import get_current_session
from app.models.session import Session, SessionRead
from app.repositories.session_repository import SessionRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sessions", tags=["Sessions"])


@router.get("/current", response_model=SessionRead)
async def get_current_session_info(
    request: Request, current_session: Session = Depends(get_current_session)
):
    """Получить информацию о текущей сессии"""
    if not current_session:
        raise HTTPException(status_code=401, detail="No active session")

    return SessionRead(
        id=current_session.id,
        session_id=current_session.session_id,
        user_agent=current_session.user_agent,
        ip_address=current_session.ip_address,
        is_active=current_session.is_active,
        expires_at=current_session.expires_at,
        last_activity=current_session.last_activity,
        created_at=current_session.created_at,
        updated_at=current_session.updated_at,
    )


@router.post("/refresh")
async def refresh_session(
    request: Request,
    current_session: Session = Depends(get_current_session),
    session_repo: SessionRepository = Depends(SessionRepository),
):
    """Продлить сессию на 30 дней"""
    if not current_session:
        raise HTTPException(status_code=401, detail="No active session")
    current_session.extend_session(days=30)

    # Обновляем через репозиторий
    await session_repo.update_last_activity(current_session.session_id)

    logger.info(f"Extended session {current_session.session_id}")

    return {
        "message": "Session extended successfully",
        "expires_at": current_session.expires_at,
        "session_id": current_session.session_id,
    }


@router.post("/logout")
async def logout(
    request: Request,
    current_session: Session = Depends(get_current_session),
    session_repo: SessionRepository = Depends(SessionRepository),
):
    """Завершить текущую сессию"""
    if not current_session:
        raise HTTPException(status_code=401, detail="No active session")
    deactivated = await session_repo.deactivate_session(current_session.session_id)

    if deactivated:
        logger.info(f"Deactivated session {current_session.session_id}")
        response = JSONResponse(content={"message": "Logged out successfully"})
        response.delete_cookie("session_id")
        return response
    else:
        raise HTTPException(status_code=500, detail="Failed to logout")


@router.get("/health")
async def session_health_check():
    """Проверка работоспособности сессионного механизма"""
    return {
        "status": "healthy",
        "service": "session_management",
        "message": "Session management is working properly",
    }
