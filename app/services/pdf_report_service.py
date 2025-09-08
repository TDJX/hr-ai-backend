import io
import os
from datetime import datetime

from jinja2 import Template
import pdfkit

from app.core.s3 import s3_service
from app.models.interview_report import InterviewReport, RecommendationType


class PDFReportService:
    """Сервис для генерации PDF отчетов по интервью на основе HTML шаблона"""

    def __init__(self):
        self.template_path = "templates/interview_report.html"
        
    def _load_html_template(self) -> str:
        """Загружает HTML шаблон из файла"""
        try:
            with open(self.template_path, 'r', encoding='utf-8') as file:
                return file.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"HTML шаблон не найден: {self.template_path}")
    
    def _format_concerns_field(self, concerns):
        """Форматирует поле concerns для отображения"""
        if not concerns:
            return "—"
        
        if isinstance(concerns, list):
            return "; ".join(concerns)
        elif isinstance(concerns, str):
            return concerns
        else:
            return str(concerns)
    
    def _get_score_class(self, score: int) -> str:
        """Возвращает CSS класс для цвета оценки"""
        if score >= 80:
            return "score-green"
        elif score >= 60:
            return "score-orange"
        else:
            return "score-red"
    
    def _format_recommendation(self, recommendation: RecommendationType) -> tuple:
        """Форматирует рекомендацию для отображения"""
        if recommendation == RecommendationType.HIRE:
            return ("Рекомендуем", "recommend-button")
        elif recommendation == RecommendationType.CONSIDER:
            return ("К рассмотрению", "consider-button")
        else:
            return ("Не рекомендуем", "reject-button")
    
    def generate_pdf_report(self, interview_report: InterviewReport) -> bytes:
        """
        Генерирует PDF отчет на основе HTML шаблона
        
        Args:
            interview_report: Данные отчета по интервью
            
        Returns:
            bytes: PDF файл в виде байтов
        """
        try:
            # Загружаем HTML шаблон
            html_template = self._load_html_template()
            
            # Подготавливаем данные для шаблона
            template_data = self._prepare_template_data(interview_report)
            
            # Рендерим HTML с данными
            template = Template(html_template)
            rendered_html = template.render(**template_data)
            
            # Настройки для wkhtmltopdf
            options = {
                'page-size': 'A4',
                'margin-top': '0.75in',
                'margin-right': '0.75in',
                'margin-bottom': '0.75in',
                'margin-left': '0.75in',
                'encoding': 'UTF-8',
                'no-outline': None,
                'enable-local-file-access': None
            }
            
            # Генерируем PDF
            pdf_bytes = pdfkit.from_string(rendered_html, False, options=options)
            
            return pdf_bytes
            
        except Exception as e:
            raise Exception(f"Ошибка при генерации PDF: {str(e)}")
    
    def _prepare_template_data(self, interview_report: InterviewReport) -> dict:
        """Подготавливает данные для HTML шаблона"""
        
        # Основная информация о кандидате
        candidate_name = interview_report.resume.applicant_name or "Не указано"
        position = "Не указана"
        
        # Получаем название позиции из связанной вакансии
        if hasattr(interview_report.resume, 'vacancy') and interview_report.resume.vacancy:
            position = interview_report.resume.vacancy.title
        
        # Форматируем дату интервью
        interview_date = "Не указана"
        if interview_report.interview_session and interview_report.interview_session.interview_start_time:
            interview_date = interview_report.interview_session.interview_start_time.strftime("%d.%m.%Y %H:%M")
        
        # Общий балл и рекомендация
        overall_score = interview_report.overall_score or 0
        recommendation_text, recommendation_class = self._format_recommendation(interview_report.recommendation)
        
        # Сильные стороны и области развития
        strengths = self._format_concerns_field(interview_report.strengths_concerns) if interview_report.strengths_concerns else "Не указаны"
        areas_for_development = self._format_concerns_field(interview_report.areas_for_development_concerns) if interview_report.areas_for_development_concerns else "Не указаны"
        
        # Детальная оценка
        evaluation_criteria = []
        
        # Технические навыки
        if interview_report.technical_skills_score is not None:
            evaluation_criteria.append({
                'name': 'Технические навыки',
                'score': interview_report.technical_skills_score,
                'score_class': self._get_score_class(interview_report.technical_skills_score),
                'justification': interview_report.technical_skills_justification or "—",
                'concerns': self._format_concerns_field(interview_report.technical_skills_concerns)
            })
        
        # Релевантность опыта
        if interview_report.experience_relevance_score is not None:
            evaluation_criteria.append({
                'name': 'Релевантность опыта',
                'score': interview_report.experience_relevance_score,
                'score_class': self._get_score_class(interview_report.experience_relevance_score),
                'justification': interview_report.experience_relevance_justification or "—",
                'concerns': self._format_concerns_field(interview_report.experience_relevance_concerns)
            })
        
        # Коммуникация
        if interview_report.communication_score is not None:
            evaluation_criteria.append({
                'name': 'Коммуникация',
                'score': interview_report.communication_score,
                'score_class': self._get_score_class(interview_report.communication_score),
                'justification': interview_report.communication_justification or "—",
                'concerns': self._format_concerns_field(interview_report.communication_concerns)
            })
        
        # Решение задач
        if interview_report.problem_solving_score is not None:
            evaluation_criteria.append({
                'name': 'Решение задач',
                'score': interview_report.problem_solving_score,
                'score_class': self._get_score_class(interview_report.problem_solving_score),
                'justification': interview_report.problem_solving_justification or "—",
                'concerns': self._format_concerns_field(interview_report.problem_solving_concerns)
            })
        
        # Культурное соответствие
        if interview_report.cultural_fit_score is not None:
            evaluation_criteria.append({
                'name': 'Культурное соответствие',
                'score': interview_report.cultural_fit_score,
                'score_class': self._get_score_class(interview_report.cultural_fit_score),
                'justification': interview_report.cultural_fit_justification or "—",
                'concerns': self._format_concerns_field(interview_report.cultural_fit_concerns)
            })
        
        # Красные флаги
        red_flags = []
        if interview_report.red_flags:
            if isinstance(interview_report.red_flags, list):
                red_flags = interview_report.red_flags
            elif isinstance(interview_report.red_flags, str):
                red_flags = [interview_report.red_flags]
        
        # Ссылка на резюме
        resume_url = interview_report.resume.file_url if interview_report.resume.file_url else "#"
        
        # ID отчета
        report_id = f"#{interview_report.id}" if interview_report.id else "#0"
        
        # Дата генерации отчета
        generation_date = datetime.now().strftime("%d.%m.%Y %H:%M")
        
        return {
            'report_id': report_id,
            'candidate_name': candidate_name,
            'position': position,
            'interview_date': interview_date,
            'overall_score': overall_score,
            'recommendation_text': recommendation_text,
            'recommendation_class': recommendation_class,
            'strengths': strengths,
            'areas_for_development': areas_for_development,
            'evaluation_criteria': evaluation_criteria,
            'red_flags': red_flags,
            'resume_url': resume_url,
            'generation_date': generation_date
        }

    async def upload_pdf_to_s3(self, pdf_bytes: bytes, filename: str) -> str:
        """
        Загружает PDF файл в S3 и возвращает публичную ссылку
        
        Args:
            pdf_bytes: PDF файл в виде байтов
            filename: Имя файла
            
        Returns:
            str: Публичная ссылка на файл в S3
        """
        try:
            pdf_stream = io.BytesIO(pdf_bytes)
            
            # Загружаем с публичным доступом
            file_url = await s3_service.upload_file(
                pdf_stream, 
                filename, 
                content_type="application/pdf",
                public=True
            )
            
            return file_url
            
        except Exception as e:
            raise Exception(f"Ошибка при загрузке PDF в S3: {str(e)}")

    async def generate_and_upload_pdf(self, report: InterviewReport, candidate_name: str = None, position: str = None) -> str:
        """
        Генерирует PDF отчет и загружает его в S3 (метод обратной совместимости)
        
        Args:
            report: Отчет по интервью
            candidate_name: Имя кандидата (не используется, берется из отчета)
            position: Позиция (не используется, берется из отчета)
            
        Returns:
            str: Публичная ссылка на PDF файл
        """
        try:
            # Генерируем PDF
            pdf_bytes = self.generate_pdf_report(report)
            
            # Создаем имя файла
            safe_name = report.resume.applicant_name or "candidate"
            safe_name = "".join(c for c in safe_name if c.isalnum() or c in (' ', '-', '_')).strip()
            filename = f"interview_report_{safe_name}_{report.id}.pdf"
            
            # Загружаем в S3
            pdf_url = await self.upload_pdf_to_s3(pdf_bytes, filename)
            
            return pdf_url
            
        except Exception as e:
            raise Exception(f"Ошибка при генерации и загрузке PDF: {str(e)}")


# Экземпляр сервиса
pdf_report_service = PDFReportService()
