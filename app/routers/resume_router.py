from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.core.session_middleware import get_current_session, get_db_session
from app.models.resume import ResumeCreate, ResumeUpdate, ResumeRead, ResumeStatus
from app.models.session import Session
from app.services.resume_service import ResumeService
from app.services.file_service import FileService
from celery_worker.tasks import parse_resume_task
from celery_worker.celery_app import celery_app

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.post("/", response_model=ResumeRead)
async def create_resume(
    request: Request,
    vacancy_id: int = Form(...),
    applicant_name: str = Form(...),
    applicant_email: str = Form(...),
    applicant_phone: Optional[str] = Form(None),
    cover_letter: Optional[str] = Form(None),
    resume_file: UploadFile = File(...),
    current_session: Session = Depends(get_current_session),
    db_session: AsyncSession = Depends(get_db_session)
):
    if not current_session:
        raise HTTPException(status_code=401, detail="No active session")
    
    file_service = FileService()
    resume_service = ResumeService(db_session)
    
    upload_result = await file_service.upload_resume_file(resume_file)
    if not upload_result:
        raise HTTPException(status_code=400, detail="Failed to upload resume file")
    
    resume_file_url, local_file_path = upload_result
    
    resume_data = ResumeCreate(
        vacancy_id=vacancy_id,
        applicant_name=applicant_name,
        applicant_email=applicant_email,
        applicant_phone=applicant_phone,
        resume_file_url=resume_file_url,
        cover_letter=cover_letter
    )
    
    # Создаем резюме в БД
    created_resume = await resume_service.create_resume_with_session(resume_data, current_session.id)
    
    # Запускаем асинхронную задачу парсинга резюме
    try:
        # Запускаем Celery task для парсинга с локальным файлом
        task_result = parse_resume_task.delay(str(created_resume.id), local_file_path)
        
        # Добавляем task_id в ответ для отслеживания статуса
        response_data = created_resume.model_dump()
        response_data["parsing_task_id"] = task_result.id
        response_data["parsing_status"] = "started"
        
        return response_data
        
    except Exception as e:
        # Если не удалось запустить парсинг, оставляем резюме в статусе PENDING
        print(f"Failed to start parsing task for resume {created_resume.id}: {str(e)}")
        return created_resume


@router.get("/", response_model=List[ResumeRead])
async def get_resumes(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    vacancy_id: Optional[int] = Query(None),
    status: Optional[ResumeStatus] = Query(None),
    current_session: Session = Depends(get_current_session),
    db_session: AsyncSession = Depends(get_db_session)
):
    if not current_session:
        raise HTTPException(status_code=401, detail="No active session")
    
    service = ResumeService(db_session)
    
    # Получаем только резюме текущего пользователя
    if vacancy_id:
        return await service.get_resumes_by_vacancy_and_session(vacancy_id, current_session.id)
    
    return await service.get_resumes_by_session(current_session.id, skip=skip, limit=limit)


@router.get("/{resume_id}", response_model=ResumeRead)
async def get_resume(
    request: Request,
    resume_id: int,
    current_session: Session = Depends(get_current_session),
    db_session: AsyncSession = Depends(get_db_session)
):
    if not current_session:
        raise HTTPException(status_code=401, detail="No active session")
    
    service = ResumeService(db_session)
    resume = await service.get_resume(resume_id)
    
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    
    # Проверяем, что резюме принадлежит текущей сессии
    if resume.session_id != current_session.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return resume


@router.put("/{resume_id}", response_model=ResumeRead)
async def update_resume(
    request: Request,
    resume_id: int,
    resume: ResumeUpdate,
    current_session: Session = Depends(get_current_session),
    db_session: AsyncSession = Depends(get_db_session)
):
    if not current_session:
        raise HTTPException(status_code=401, detail="No active session")
    
    service = ResumeService(db_session)
    existing_resume = await service.get_resume(resume_id)
    
    if not existing_resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    
    # Проверяем, что резюме принадлежит текущей сессии
    if existing_resume.session_id != current_session.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    updated_resume = await service.update_resume(resume_id, resume)
    return updated_resume


@router.patch("/{resume_id}/status", response_model=ResumeRead)
async def update_resume_status(
    request: Request,
    resume_id: int,
    status: ResumeStatus,
    current_session: Session = Depends(get_current_session),
    db_session: AsyncSession = Depends(get_db_session)
):
    if not current_session:
        raise HTTPException(status_code=401, detail="No active session")
    
    service = ResumeService(db_session)
    existing_resume = await service.get_resume(resume_id)
    
    if not existing_resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    
    # Проверяем, что резюме принадлежит текущей сессии
    if existing_resume.session_id != current_session.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    updated_resume = await service.update_resume_status(resume_id, status)
    return updated_resume


@router.post("/{resume_id}/interview-report")
async def upload_interview_report(
    request: Request,
    resume_id: int,
    report_file: UploadFile = File(...),
    current_session: Session = Depends(get_current_session),
    db_session: AsyncSession = Depends(get_db_session)
):
    if not current_session:
        raise HTTPException(status_code=401, detail="No active session")
    
    file_service = FileService()
    resume_service = ResumeService(db_session)
    
    existing_resume = await resume_service.get_resume(resume_id)
    if not existing_resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    
    # Проверяем, что резюме принадлежит текущей сессии
    if existing_resume.session_id != current_session.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    report_url = await file_service.upload_interview_report(report_file)
    if not report_url:
        raise HTTPException(status_code=400, detail="Failed to upload interview report")
    
    updated_resume = await resume_service.add_interview_report(resume_id, report_url)
    
    return {"message": "Interview report uploaded successfully", "report_url": report_url}


@router.get("/{resume_id}/parsing-status")
async def get_parsing_status(
    request: Request,
    resume_id: int,
    task_id: str = Query(..., description="Task ID from resume upload response"),
    current_session: Session = Depends(get_current_session),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Получить статус парсинга резюме по task_id"""
    if not current_session:
        raise HTTPException(status_code=401, detail="No active session")
    
    # Проверяем доступ к резюме
    service = ResumeService(db_session)
    resume = await service.get_resume(resume_id)
    
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    
    if resume.session_id != current_session.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Получаем статус задачи из Celery
    try:
        task_result = celery_app.AsyncResult(task_id)
        
        response = {
            "task_id": task_id,
            "task_state": task_result.state,
            "resume_status": resume.status,
        }
        
        if task_result.state == 'PENDING':
            response.update({
                "status": "В очереди на обработку",
                "progress": 0
            })
        elif task_result.state == 'PROGRESS':
            response.update({
                "status": task_result.info.get('status', 'Обрабатывается'),
                "progress": task_result.info.get('progress', 0)
            })
        elif task_result.state == 'SUCCESS':
            response.update({
                "status": "Завершено успешно",
                "progress": 100,
                "result": task_result.info
            })
        elif task_result.state == 'FAILURE':
            response.update({
                "status": f"Ошибка: {str(task_result.info)}",
                "progress": 0,
                "error": str(task_result.info)
            })
        
        return response
        
    except Exception as e:
        return {
            "task_id": task_id,
            "task_state": "UNKNOWN",
            "resume_status": resume.status,
            "error": f"Failed to get task status: {str(e)}"
        }


@router.delete("/{resume_id}")
async def delete_resume(
    request: Request,
    resume_id: int,
    current_session: Session = Depends(get_current_session),
    db_session: AsyncSession = Depends(get_db_session)
):
    if not current_session:
        raise HTTPException(status_code=401, detail="No active session")
    
    service = ResumeService(db_session)
    existing_resume = await service.get_resume(resume_id)
    
    if not existing_resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    
    # Проверяем, что резюме принадлежит текущей сессии
    if existing_resume.session_id != current_session.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    success = await service.delete_resume(resume_id)
    return {"message": "Resume deleted successfully"}