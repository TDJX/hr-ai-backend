
from fastapi import APIRouter, Depends, HTTPException

from app.core.session_middleware import get_current_session
from app.models.interview_report import InterviewReport
from app.models.session import Session
from app.services.interview_reports_service import InterviewReportService

router = APIRouter(prefix="/interview-reports", tags=["interview-reports"])


@router.get("/vacancy/{vacancy_id}", response_model=list[InterviewReport])
async def get_reports_by_vacancy(
    vacancy_id: int,
    current_session: Session = Depends(get_current_session),
    report_service: InterviewReportService = Depends(InterviewReportService),
):
    """Получить все отчёты по вакансии"""
    if not current_session:
        raise HTTPException(status_code=401, detail="No active session")

    reports = await report_service.get_reports_by_vacancy(vacancy_id)
    return reports


@router.get("/session/{session_id}", response_model=InterviewReport)
async def get_report_by_session(
    session_id: int,
    current_session: Session = Depends(get_current_session),
    report_service: InterviewReportService = Depends(InterviewReportService),
):
    """Получить отчёт по сессии интервью"""
    if not current_session:
        raise HTTPException(status_code=401, detail="No active session")

    report = await report_service.get_report_by_session(session_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    return report


@router.patch("/{report_id}/scores")
async def update_report_scores(
    report_id: int,
    scores: dict,
    current_session: Session = Depends(get_current_session),
    report_service: InterviewReportService = Depends(InterviewReportService),
):
    """Обновить оценки отчёта"""
    if not current_session:
        raise HTTPException(status_code=401, detail="No active session")

    success = await report_service.update_report_scores(report_id, scores)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update report scores")

    return {"message": "Report scores updated successfully"}


@router.patch("/{report_id}/notes")
async def update_report_notes(
    report_id: int,
    notes: str,
    current_session: Session = Depends(get_current_session),
    report_service: InterviewReportService = Depends(InterviewReportService),
):
    """Обновить заметки интервьюера"""
    if not current_session:
        raise HTTPException(status_code=401, detail="No active session")

    success = await report_service.update_interviewer_notes(report_id, notes)
    if not success:
        raise HTTPException(
            status_code=500, detail="Failed to update interviewer notes"
        )

    return {"message": "Interviewer notes updated successfully"}


@router.patch("/{report_id}/pdf")
async def update_report_pdf(
    report_id: int,
    pdf_url: str,
    current_session: Session = Depends(get_current_session),
    report_service: InterviewReportService = Depends(InterviewReportService),
):
    """Обновить PDF отчёта"""
    if not current_session:
        raise HTTPException(status_code=401, detail="No active session")

    success = await report_service.update_pdf_url(report_id, pdf_url)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update PDF URL")

    return {"message": "PDF URL updated successfully"}


@router.post("/create")
async def create_report(
    report_data: dict,
    current_session: Session = Depends(get_current_session),
    report_service: InterviewReportService = Depends(InterviewReportService),
):
    """Создать новый отчёт интервью"""
    if not current_session:
        raise HTTPException(status_code=401, detail="No active session")

    report = await report_service.create_report(**report_data)
    if not report:
        raise HTTPException(status_code=500, detail="Failed to create report")

    return report
