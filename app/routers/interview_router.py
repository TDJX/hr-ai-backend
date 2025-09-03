from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.session_middleware import get_current_session, get_db_session
from app.models.session import Session
from app.models.interview import InterviewValidationResponse, LiveKitTokenResponse, InterviewStatus
from app.services.interview_service import InterviewRoomService
from app.services.agent_manager import agent_manager, AgentStatus

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


@router.post("/{resume_id}/start")
async def start_interview_session(
    request: Request,
    resume_id: int,
    current_session: Session = Depends(get_current_session),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Запуск AI интервью"""
    if not current_session:
        raise HTTPException(status_code=401, detail="No active session")
    
    # Проверяем статус агента
    agent_status_info = agent_manager.get_status()
    if agent_status_info["status"] == AgentStatus.BUSY.value:
        raise HTTPException(
            status_code=409, 
            detail=f"AI Agent is busy with another interview (ID: {agent_status_info['current_interview_id']})"
        )
    
    if agent_status_info["status"] != AgentStatus.IDLE.value:
        raise HTTPException(
            status_code=503,
            detail=f"AI Agent is not ready (status: {agent_status_info['status']})"
        )
    
    interview_service = InterviewRoomService(db_session)
    
    # Валидируем резюме
    validation_result = await interview_service.validate_resume_for_interview(resume_id)
    if not validation_result.can_interview:
        raise HTTPException(status_code=400, detail=validation_result.message)
    
    # Получаем план интервью из резюме
    resume = await interview_service.get_resume_with_interview_plan(resume_id)
    if not resume or not resume.interview_plan:
        raise HTTPException(
            status_code=400, 
            detail="Resume not found or interview plan not generated"
        )
    
    # Создаем сессию интервью
    interview_session = await interview_service.create_interview_session(resume_id)
    if not interview_session:
        raise HTTPException(status_code=500, detail="Failed to create interview session")
    
    # Запускаем AI агента
    success = await agent_manager.start_interview(
        interview_id=interview_session.id,
        interview_plan=resume.interview_plan,
        room_name=interview_session.room_name
    )
    
    if not success:
        # Удаляем созданную сессию если агент не запустился
        await interview_service.delete_interview_session(interview_session.id)
        raise HTTPException(status_code=500, detail="Failed to start AI interviewer")
    
    return {
        "message": "Interview started successfully",
        "interview_id": interview_session.id,
        "room_name": interview_session.room_name,
        "agent_status": agent_manager.status.value
    }


@router.post("/{resume_id}/stop")
async def stop_interview_session(
    request: Request,
    resume_id: int,
    current_session: Session = Depends(get_current_session),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Остановка AI интервью"""
    if not current_session:
        raise HTTPException(status_code=401, detail="No active session")
    
    interview_service = InterviewRoomService(db_session)
    
    # Получаем активную сессию
    interview_session = await interview_service.get_interview_session(resume_id)
    if not interview_session:
        raise HTTPException(status_code=404, detail="No active interview session found")
    
    # Останавливаем AI агента
    success = await agent_manager.stop_interview()
    if not success:
        raise HTTPException(status_code=500, detail="Failed to stop AI interviewer")
    
    # Обновляем статус сессии в БД
    await interview_service.update_session_status(interview_session.id, "completed")
    
    return {
        "message": "Interview stopped successfully",
        "interview_id": interview_session.id,
        "agent_status": agent_manager.status.value
    }


@router.get("/{resume_id}/status")
async def get_interview_status(
    request: Request,
    resume_id: int,
    current_session: Session = Depends(get_current_session),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Получение статуса интервью"""
    if not current_session:
        raise HTTPException(status_code=401, detail="No active session")
    
    interview_service = InterviewRoomService(db_session)
    
    # Получаем сессию интервью
    interview_session = await interview_service.get_interview_session(resume_id)
    
    agent_status_info = agent_manager.get_status()
    
    return {
        "resume_id": resume_id,
        "interview_session": {
            "id": interview_session.id if interview_session else None,
            "room_name": interview_session.room_name if interview_session else None,
            "status": interview_session.status if interview_session else "not_started",
            "started_at": interview_session.started_at if interview_session else None,
        },
        "agent_status": agent_status_info,
        "can_start_interview": (
            agent_status_info["status"] == AgentStatus.IDLE.value and
            (not interview_session or interview_session.status != "active")
        )
    }


@router.get("/{resume_id}/transcript") 
async def get_interview_transcript(
    request: Request,
    resume_id: int,
    current_session: Session = Depends(get_current_session),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Получение расшифровки интервью"""
    if not current_session:
        raise HTTPException(status_code=401, detail="No active session")
    
    interview_service = InterviewRoomService(db_session)
    
    # Получаем сессию интервью
    interview_session = await interview_service.get_interview_session(resume_id)
    if not interview_session:
        raise HTTPException(status_code=404, detail="Interview session not found")
    
    return {
        "interview_id": interview_session.id,
        "transcript": interview_session.transcript or "No transcript available yet",
        "status": interview_session.status,
        "started_at": interview_session.started_at,
        "completed_at": interview_session.completed_at
    }


@router.patch("/{resume_id}/end")
async def end_interview(
    request: Request,
    resume_id: int,
    current_session: Session = Depends(get_current_session),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Завершение собеседования (legacy endpoint)"""
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