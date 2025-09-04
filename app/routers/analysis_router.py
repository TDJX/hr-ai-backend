# -*- coding: utf-8 -*-
from typing import List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel

from app.repositories.resume_repository import ResumeRepository
from celery_worker.interview_analysis_task import generate_interview_report, analyze_multiple_candidates


router = APIRouter(
    prefix="/analysis",
    tags=["analysis"]
)


class AnalysisResponse(BaseModel):
    """Ответ запуска задачи анализа"""
    message: str
    resume_id: int
    task_id: str


class BulkAnalysisRequest(BaseModel):
    """Запрос массового анализа"""
    resume_ids: List[int]


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


@router.post("/interview-report/{resume_id}", response_model=AnalysisResponse)
async def start_interview_analysis(
    resume_id: int,
    background_tasks: BackgroundTasks,
    resume_repo: ResumeRepository = Depends(ResumeRepository)
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
        message="Interview analysis started",
        resume_id=resume_id,
        task_id=task.id
    )


@router.post("/bulk-analysis", response_model=BulkAnalysisResponse)
async def start_bulk_analysis(
    request: BulkAnalysisRequest,
    background_tasks: BackgroundTasks,
    resume_repo: ResumeRepository = Depends(ResumeRepository)
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
        task_id=task.id
    )


@router.get("/ranking/{vacancy_id}")
async def get_candidates_ranking(
    vacancy_id: int,
    resume_repo: ResumeRepository = Depends(ResumeRepository)
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
            "message": "No interviewed candidates found"
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
        "resume_ids": resume_ids
    }


@router.get("/report/{resume_id}")
async def get_interview_report(
    resume_id: int,
    resume_repo: ResumeRepository = Depends(ResumeRepository)
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
            "message": "Report available"
        }
    
    # Если отчета нет - запускаем анализ
    task = generate_interview_report.delay(resume_id)
    
    return {
        "resume_id": resume_id,
        "candidate_name": resume.applicant_name,
        "status": "in_progress",
        "task_id": task.id,
        "message": "Analysis started, check back later"
    }


@router.get("/statistics/{vacancy_id}")
async def get_analysis_statistics(
    vacancy_id: int,
    resume_repo: ResumeRepository = Depends(ResumeRepository)
):
    """
    Получить статистику анализа кандидатов по вакансии
    """
    
    resumes = await resume_repo.get_by_vacancy_id(vacancy_id)
    
    total_candidates = len(resumes)
    interviewed = len([r for r in resumes if r.status == "interviewed"])
    with_reports = len([r for r in resumes if r.notes and "ОЦЕНКА КАНДИДАТА" in r.notes])
    
    # Подсчитываем рекомендации из notes (упрощенно)
    recommendations = {"strongly_recommend": 0, "recommend": 0, "consider": 0, "reject": 0}
    
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
            "analysis_completion": round((with_reports / max(interviewed, 1)) * 100, 1) if interviewed > 0 else 0
        }
    }