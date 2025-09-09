from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.core.database import get_session
from app.repositories.resume_repository import ResumeRepository
from celery_worker.interview_analysis_task import (
    analyze_multiple_candidates,
    generate_interview_report,
)

router = APIRouter(prefix="/analysis", tags=["analysis"])


class AnalysisResponse(BaseModel):
    """Ответ запуска задачи анализа"""

    message: str
    resume_id: int
    task_id: str


class BulkAnalysisRequest(BaseModel):
    """Запрос массового анализа"""

    resume_ids: list[int]


class BulkAnalysisResponse(BaseModel):
    """Ответ массового анализа"""

    message: str
    resume_count: int
    task_id: str


class CandidateRanking(BaseModel):
    """Рейтинг кандидата"""

    resume_id: int
    candidate_name: str
    overall_score: int
    recommendation: str
    position: str


class PDFGenerationResponse(BaseModel):
    """Ответ генерации PDF отчета"""

    message: str
    resume_id: int
    candidate_name: str
    pdf_url: str | None = None
    status: str  # "generated", "exists", "failed"


@router.post("/interview-report/{resume_id}", response_model=AnalysisResponse)
async def start_interview_analysis(
    resume_id: int,
    background_tasks: BackgroundTasks,
    resume_repo: ResumeRepository = Depends(ResumeRepository),
):
    """
    Запускает анализ интервью для конкретного кандидата

    Анализирует:
    - Соответствие резюме вакансии
    - Качество ответов в диалоге интервью
    - Технические навыки и опыт
    - Коммуникативные способности
    - Общую рекомендацию и рейтинг
    """

    # Проверяем, существует ли резюме
    resume = await resume_repo.get_by_id(resume_id)

    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    # Запускаем задачу анализа
    task = generate_interview_report.delay(resume_id)

    return AnalysisResponse(
        message="Interview analysis started", resume_id=resume_id, task_id=task.id
    )


@router.post("/bulk-analysis", response_model=BulkAnalysisResponse)
async def start_bulk_analysis(
    request: BulkAnalysisRequest,
    background_tasks: BackgroundTasks,
    resume_repo: ResumeRepository = Depends(ResumeRepository),
):
    """
    Запускает массовый анализ нескольких кандидатов

    Возвращает ранжированный список кандидатов по общему баллу
    Полезно для сравнения кандидатов на одну позицию
    """

    # Проверяем, что все резюме существуют
    existing_resumes = []

    for resume_id in request.resume_ids:
        resume = await resume_repo.get_by_id(resume_id)
        if resume:
            existing_resumes.append(resume_id)

    if not existing_resumes:
        raise HTTPException(status_code=404, detail="No valid resumes found")

    # Запускаем задачу массового анализа
    task = analyze_multiple_candidates.delay(existing_resumes)

    return BulkAnalysisResponse(
        message="Bulk analysis started",
        resume_count=len(existing_resumes),
        task_id=task.id,
    )


@router.get("/ranking/{vacancy_id}")
async def get_candidates_ranking(
    vacancy_id: int, resume_repo: ResumeRepository = Depends(ResumeRepository)
):
    """
    Получить ранжированный список кандидатов для вакансии

    Сортирует кандидатов по результатам анализа интервью
    Показывает только тех, кто прошел интервью
    """

    # Получаем все резюме для вакансии со статусом "interviewed"
    resumes = await resume_repo.get_by_vacancy_id(vacancy_id)
    interviewed_resumes = [r for r in resumes if r.status in ["interviewed"]]

    if not interviewed_resumes:
        return {
            "vacancy_id": vacancy_id,
            "candidates": [],
            "message": "No interviewed candidates found",
        }

    # Запускаем массовый анализ если еще не было
    resume_ids = [r.id for r in interviewed_resumes]
    task = analyze_multiple_candidates.delay(resume_ids)

    # В реальности здесь нужно дождаться выполнения или получить из кэша
    # Пока возвращаем информацию о запущенной задаче
    return {
        "vacancy_id": vacancy_id,
        "task_id": task.id,
        "message": f"Analysis started for {len(resume_ids)} candidates",
        "resume_ids": resume_ids,
    }


@router.get("/report/{resume_id}")
async def get_interview_report(
    resume_id: int, resume_repo: ResumeRepository = Depends(ResumeRepository)
):
    """
    Получить готовый отчет анализа интервью

    Если отчет еще не готов - запускает анализ
    """

    resume = await resume_repo.get_by_id(resume_id)

    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    # Проверяем, есть ли уже готовый отчет в notes
    if resume.notes and "ОЦЕНКА КАНДИДАТА" in resume.notes:
        return {
            "resume_id": resume_id,
            "candidate_name": resume.applicant_name,
            "status": "completed",
            "report_summary": resume.notes,
            "message": "Report available",
        }

    # Если отчета нет - запускаем анализ
    task = generate_interview_report.delay(resume_id)

    return {
        "resume_id": resume_id,
        "candidate_name": resume.applicant_name,
        "status": "in_progress",
        "task_id": task.id,
        "message": "Analysis started, check back later",
    }


@router.get("/statistics/{vacancy_id}")
async def get_analysis_statistics(
    vacancy_id: int, resume_repo: ResumeRepository = Depends(ResumeRepository)
):
    """
    Получить статистику анализа кандидатов по вакансии
    """

    resumes = await resume_repo.get_by_vacancy_id(vacancy_id)

    total_candidates = len(resumes)
    interviewed = len([r for r in resumes if r.status == "interviewed"])
    with_reports = len(
        [r for r in resumes if r.notes and "ОЦЕНКА КАНДИДАТА" in r.notes]
    )

    # Подсчитываем рекомендации из notes (упрощенно)
    recommendations = {
        "strongly_recommend": 0,
        "recommend": 0,
        "consider": 0,
        "reject": 0,
    }

    for resume in resumes:
        if resume.notes and "ОЦЕНКА КАНДИДАТА" in resume.notes:
            notes = resume.notes.lower()
            if "strongly_recommend" in notes:
                recommendations["strongly_recommend"] += 1
            elif "recommend" in notes and "strongly_recommend" not in notes:
                recommendations["recommend"] += 1
            elif "consider" in notes:
                recommendations["consider"] += 1
            elif "reject" in notes:
                recommendations["reject"] += 1

    return {
        "vacancy_id": vacancy_id,
        "statistics": {
            "total_candidates": total_candidates,
            "interviewed_candidates": interviewed,
            "analyzed_candidates": with_reports,
            "recommendations": recommendations,
            "analysis_completion": round((with_reports / max(interviewed, 1)) * 100, 1)
            if interviewed > 0
            else 0,
        },
    }


@router.get("/pdf-report/{resume_id}")
async def get_pdf_report(
    resume_id: int,
    session=Depends(get_session),
    resume_repo: ResumeRepository = Depends(ResumeRepository),
):
    """
    Получить PDF отчет по интервью

    Если отчет готов - перенаправляет на S3 URL
    Если отчета нет - возвращает информацию о статусе
    """
    from sqlmodel import select

    from app.models.interview import InterviewSession
    from app.models.interview_report import InterviewReport

    # Проверяем, существует ли резюме
    resume = await resume_repo.get_by_id(resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    # Ищем сессию интервью и отчет
    statement = (
        select(InterviewReport, InterviewSession)
        .join(
            InterviewSession,
            InterviewReport.interview_session_id == InterviewSession.id,
        )
        .where(InterviewSession.resume_id == resume_id)
    )

    result = await session.execute(statement)
    report_session = result.first()

    if not report_session:
        # Если отчета нет - возможно, нужно запустить анализ
        raise HTTPException(
            status_code=404,
            detail="Interview report not found. Run analysis first using POST /analysis/interview-report/{resume_id}",
        )

    report, interview_session = report_session

    if not report.pdf_report_url:
        # PDF еще не сгенерирован
        return {
            "status": "pdf_not_ready",
            "message": "PDF report is being generated or failed to generate",
            "report_id": report.id,
            "candidate_name": resume.applicant_name,
        }

    # Перенаправляем на S3 URL
    return RedirectResponse(url=report.pdf_report_url, status_code=302)


@router.post("/generate-pdf/{resume_id}")
async def generate_pdf_report(
    resume_id: int,
    session=Depends(get_session),
    resume_repo: ResumeRepository = Depends(ResumeRepository),
):
    """
    Запускает асинхронную генерацию PDF отчета по интервью

    Проверяет наличие отчета в базе данных и запускает Celery задачу для генерации PDF файла.
    Если PDF уже существует, возвращает существующий URL.
    """
    from sqlmodel import select

    from app.models.interview import InterviewSession
    from app.models.interview_report import InterviewReport
    from celery_worker.tasks import generate_pdf_report_task

    # Проверяем, существует ли резюме
    resume = await resume_repo.get_by_id(resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    # Ищем отчет интервью
    statement = (
        select(InterviewReport, InterviewSession)
        .join(
            InterviewSession,
            InterviewReport.interview_session_id == InterviewSession.id,
        )
        .where(InterviewSession.resume_id == resume_id)
    )

    result = await session.execute(statement)
    report_session = result.first()

    if not report_session:
        raise HTTPException(
            status_code=404,
            detail="Interview report not found. Run analysis first using POST /analysis/interview-report/{resume_id}",
        )

    report, interview_session = report_session

    # Если PDF уже существует, возвращаем его
    if report.pdf_report_url:
        return {
            "message": "PDF report already exists",
            "resume_id": resume_id,
            "report_id": report.id,
            "candidate_name": resume.applicant_name,
            "pdf_url": report.pdf_report_url,
            "status": "exists",
        }

    # Получаем позицию из связанной вакансии
    from app.models.vacancy import Vacancy

    vacancy_stmt = select(Vacancy).where(Vacancy.id == resume.vacancy_id)
    vacancy_result = await session.execute(vacancy_stmt)
    vacancy = vacancy_result.scalar_one_or_none()

    position = vacancy.title if vacancy else "Позиция не указана"

    # Сериализуем данные отчета
    report_data = {
        "id": report.id,
        "interview_session_id": report.interview_session_id,
        "technical_skills_score": report.technical_skills_score,
        "technical_skills_justification": report.technical_skills_justification,
        "technical_skills_concerns": report.technical_skills_concerns,
        "experience_relevance_score": report.experience_relevance_score,
        "experience_relevance_justification": report.experience_relevance_justification,
        "experience_relevance_concerns": report.experience_relevance_concerns,
        "communication_score": report.communication_score,
        "communication_justification": report.communication_justification,
        "communication_concerns": report.communication_concerns,
        "problem_solving_score": report.problem_solving_score,
        "problem_solving_justification": report.problem_solving_justification,
        "problem_solving_concerns": report.problem_solving_concerns,
        "cultural_fit_score": report.cultural_fit_score,
        "cultural_fit_justification": report.cultural_fit_justification,
        "cultural_fit_concerns": report.cultural_fit_concerns,
        "overall_score": report.overall_score,
        "recommendation": report.recommendation,
        "strengths": report.strengths,
        "weaknesses": report.weaknesses,
        "red_flags": report.red_flags,
        "questions_quality_score": report.questions_quality_score,
        "interview_duration_minutes": report.interview_duration_minutes,
        "response_count": report.response_count,
        "dialogue_messages_count": report.dialogue_messages_count,
        "next_steps": report.next_steps,
        "interviewer_notes": report.interviewer_notes,
        "questions_analysis": report.questions_analysis,
        "analysis_method": report.analysis_method,
        "llm_model_used": report.llm_model_used,
        "analysis_duration_seconds": report.analysis_duration_seconds,
        "pdf_report_url": report.pdf_report_url,
        "created_at": report.created_at.isoformat() if report.created_at else None,
        "updated_at": report.updated_at.isoformat() if report.updated_at else None,
    }

    # Запускаем Celery задачу для генерации PDF
    task = generate_pdf_report_task.delay(
        report_data=report_data,
        candidate_name=resume.applicant_name,
        position=position,
        resume_file_url=resume.resume_file_url,
    )

    return {
        "message": "PDF generation started",
        "resume_id": resume_id,
        "report_id": report.id,
        "candidate_name": resume.applicant_name,
        "task_id": task.id,
        "status": "in_progress",
    }


@router.get("/pdf-task-status/{task_id}")
async def get_pdf_task_status(task_id: str):
    """
    Получить статус выполнения Celery задачи генерации PDF
    """
    from celery_worker.celery_app import celery_app

    try:
        task_result = celery_app.AsyncResult(task_id)

        if task_result.state == "PENDING":
            return {
                "task_id": task_id,
                "status": "pending",
                "message": "Task is waiting to be processed",
            }
        elif task_result.state == "PROGRESS":
            return {
                "task_id": task_id,
                "status": "in_progress",
                "progress": task_result.info.get("progress", 0),
                "message": task_result.info.get("status", "Processing..."),
            }
        elif task_result.state == "SUCCESS":
            result = task_result.result
            return {
                "task_id": task_id,
                "status": "completed",
                "progress": 100,
                "message": "PDF generation completed successfully",
                "pdf_url": result.get("pdf_url"),
                "file_size": result.get("file_size"),
                "report_id": result.get("interview_report_id"),
            }
        elif task_result.state == "FAILURE":
            return {
                "task_id": task_id,
                "status": "failed",
                "message": str(task_result.info),
                "error": str(task_result.info),
            }
        else:
            return {
                "task_id": task_id,
                "status": task_result.state.lower(),
                "message": f"Task state: {task_result.state}",
            }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error checking task status: {str(e)}"
        )


@router.get("/report-data/{resume_id}")
async def get_report_data(
    resume_id: int,
    session=Depends(get_session),
    resume_repo: ResumeRepository = Depends(ResumeRepository),
):
    """
    Получить данные отчета в JSON формате (без PDF)
    """
    from sqlmodel import select

    from app.models.interview import InterviewSession
    from app.models.interview_report import InterviewReport

    # Проверяем, существует ли резюме
    resume = await resume_repo.get_by_id(resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    # Ищем отчет
    statement = (
        select(InterviewReport, InterviewSession)
        .join(
            InterviewSession,
            InterviewReport.interview_session_id == InterviewSession.id,
        )
        .where(InterviewSession.resume_id == resume_id)
    )

    result = await session.execute(statement)
    report_session = result.first()

    if not report_session:
        raise HTTPException(status_code=404, detail="Interview report not found")

    report, interview_session = report_session

    # Получаем позицию из связанной вакансии
    from app.models.vacancy import Vacancy

    vacancy_stmt = select(Vacancy).where(Vacancy.id == resume.vacancy_id)
    vacancy_result = await session.execute(vacancy_stmt)
    vacancy = vacancy_result.scalar_one_or_none()

    position = vacancy.title if vacancy else "Позиция не указана"

    return {
        "report_id": report.id,
        "candidate_name": resume.applicant_name,
        "position": position,
        "interview_date": report.created_at.isoformat(),
        "overall_score": report.overall_score,
        "recommendation": report.recommendation.value,
        "scores": {
            "technical_skills": {
                "score": report.technical_skills_score,
                "justification": report.technical_skills_justification,
                "concerns": report.technical_skills_concerns,
            },
            "experience_relevance": {
                "score": report.experience_relevance_score,
                "justification": report.experience_relevance_justification,
                "concerns": report.experience_relevance_concerns,
            },
            "communication": {
                "score": report.communication_score,
                "justification": report.communication_justification,
                "concerns": report.communication_concerns,
            },
            "problem_solving": {
                "score": report.problem_solving_score,
                "justification": report.problem_solving_justification,
                "concerns": report.problem_solving_concerns,
            },
            "cultural_fit": {
                "score": report.cultural_fit_score,
                "justification": report.cultural_fit_justification,
                "concerns": report.cultural_fit_concerns,
            },
        },
        "strengths": report.strengths,
        "weaknesses": report.weaknesses,
        "red_flags": report.red_flags,
        "next_steps": report.next_steps,
        "metrics": {
            "interview_duration_minutes": report.interview_duration_minutes,
            "dialogue_messages_count": report.dialogue_messages_count,
            "questions_quality_score": report.questions_quality_score,
        },
        "pdf_available": bool(report.pdf_report_url),
        "pdf_url": report.pdf_report_url,
        "analysis_metadata": {
            "method": report.analysis_method,
            "model_used": report.llm_model_used,
            "analysis_duration": report.analysis_duration_seconds,
        },
    }
