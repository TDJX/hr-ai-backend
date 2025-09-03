from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.session_middleware import get_current_session, get_db_session
from app.models.session import Session
from app.models.interview import InterviewValidationResponse, LiveKitTokenResponse, InterviewStatus
from app.services.interview_service import InterviewRoomService

router = APIRouter(prefix="/interview", tags=["interview"])


@router.get("/{resume_id}/validate-interview", response_model=InterviewValidationResponse)
async def validate_interview(
    request: Request,
    resume_id: int,
    current_session: Session = Depends(get_current_session),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Валидация резюме для проведения собеседования"""
    if not current_session:
        raise HTTPException(status_code=401, detail="No active session")
    
    interview_service = InterviewRoomService(db_session)
    
    # Проверяем валидность резюме для собеседования
    validation_result = await interview_service.validate_resume_for_interview(resume_id)
    
    # Если резюме не найдено, возвращаем 404
    if "not found" in validation_result.message.lower():
        raise HTTPException(status_code=404, detail=validation_result.message)
    
    # Если резюме не готово, возвращаем 400
    if not validation_result.can_interview and "not ready" in validation_result.message.lower():
        raise HTTPException(status_code=400, detail=validation_result.message)
    
    return validation_result


@router.post("/{resume_id}/token", response_model=LiveKitTokenResponse)
async def get_interview_token(
    request: Request,
    resume_id: int,
    current_session: Session = Depends(get_current_session),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Получение токена для LiveKit собеседования"""
    if not current_session:
        raise HTTPException(status_code=401, detail="No active session")
    
    interview_service = InterviewRoomService(db_session)
    
    # Получаем токен для LiveKit
    token_response = await interview_service.get_livekit_token(resume_id)
    
    if not token_response:
        raise HTTPException(
            status_code=400, 
            detail="Cannot create interview session. Check if resume is ready for interview."
        )
    
    return token_response


@router.patch("/{resume_id}/end")
async def end_interview(
    request: Request,
    resume_id: int,
    current_session: Session = Depends(get_current_session),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Завершение собеседования"""
    if not current_session:
        raise HTTPException(status_code=401, detail="No active session")
    
    interview_service = InterviewRoomService(db_session)
    
    # Получаем активную сессию собеседования
    interview_session = await interview_service.get_interview_session(resume_id)
    
    if not interview_session:
        raise HTTPException(status_code=404, detail="No active interview session found")
    
    # Завершаем сессию
    success = await interview_service.update_session_status(
        interview_session.id, 
        "completed"
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to end interview session")
    
    return {"message": "Interview session ended successfully"}