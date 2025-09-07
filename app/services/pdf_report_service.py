import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.core.s3 import s3_service
from app.models.interview_report import InterviewReport, RecommendationType


class PDFReportService:
    """Сервис для генерации PDF отчетов по интервью"""

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Настройка кастомных стилей для документа"""
        # Заголовок отчета
        self.styles.add(
            ParagraphStyle(
                name="ReportTitle",
                parent=self.styles["Title"],
                fontSize=18,
                spaceAfter=30,
                alignment=TA_CENTER,
                textColor=colors.HexColor("#2E3440"),
                fontName="Helvetica-Bold",
            )
        )

        # Заголовки секций
        self.styles.add(
            ParagraphStyle(
                name="SectionHeader",
                parent=self.styles["Heading1"],
                fontSize=14,
                spaceAfter=12,
                spaceBefore=20,
                textColor=colors.HexColor("#5E81AC"),
                fontName="Helvetica-Bold",
            )
        )

        # Подзаголовки
        self.styles.add(
            ParagraphStyle(
                name="SubHeader",
                parent=self.styles["Heading2"],
                fontSize=12,
                spaceAfter=8,
                spaceBefore=15,
                textColor=colors.HexColor("#81A1C1"),
                fontName="Helvetica-Bold",
            )
        )

        # Обычный текст
        self.styles.add(
            ParagraphStyle(
                name="BodyText",
                parent=self.styles["Normal"],
                fontSize=10,
                spaceAfter=6,
                alignment=TA_JUSTIFY,
                textColor=colors.HexColor("#2E3440"),
            )
        )

        # Стиль для метрик
        self.styles.add(
            ParagraphStyle(
                name="MetricValue",
                parent=self.styles["Normal"],
                fontSize=12,
                alignment=TA_CENTER,
                textColor=colors.HexColor("#5E81AC"),
                fontName="Helvetica-Bold",
            )
        )

    async def generate_interview_report_pdf(
        self, report: InterviewReport, candidate_name: str, position: str
    ) -> bytes:
        """
        Генерирует PDF отчет по интервью

        Args:
            report: Модель отчета из БД
            candidate_name: Имя кандидата
            position: Название позиции

        Returns:
            bytes: PDF файл в виде байтов
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72,
        )

        # Собираем элементы документа
        story = []

        # Заголовок отчета
        story.append(
            Paragraph(
                f"Отчет по собеседованию<br/>{candidate_name}",
                self.styles["ReportTitle"],
            )
        )

        # Основная информация
        story.append(Paragraph("Основная информация", self.styles["SectionHeader"]))

        basic_info = [
            ["Кандидат:", candidate_name],
            ["Позиция:", position],
            ["Дата интервью:", report.created_at.strftime("%d.%m.%Y %H:%M")],
            ["Общий балл:", f"<b>{report.overall_score}/100</b>"],
            ["Рекомендация:", self._format_recommendation(report.recommendation)],
        ]

        basic_table = Table(basic_info, colWidths=[2 * inch, 4 * inch])
        basic_table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(basic_table)
        story.append(Spacer(1, 20))

        # Оценки по критериям
        story.append(Paragraph("Детальная оценка", self.styles["SectionHeader"]))

        criteria_data = [
            ["Критерий", "Балл", "Обоснование", "Риски"],
            [
                "Технические навыки",
                f"{report.technical_skills_score}/100",
                report.technical_skills_justification or "—",
                report.technical_skills_concerns or "—",
            ],
            [
                "Релевантность опыта",
                f"{report.experience_relevance_score}/100",
                report.experience_relevance_justification or "—",
                report.experience_relevance_concerns or "—",
            ],
            [
                "Коммуникация",
                f"{report.communication_score}/100",
                report.communication_justification or "—",
                report.communication_concerns or "—",
            ],
            [
                "Решение задач",
                f"{report.problem_solving_score}/100",
                report.problem_solving_justification or "—",
                report.problem_solving_concerns or "—",
            ],
            [
                "Культурное соответствие",
                f"{report.cultural_fit_score}/100",
                report.cultural_fit_justification or "—",
                report.cultural_fit_concerns or "—",
            ],
        ]

        criteria_table = Table(
            criteria_data, colWidths=[2 * inch, 0.8 * inch, 2.2 * inch, 1.8 * inch]
        )
        criteria_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#5E81AC")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("ALIGN", (1, 1), (1, -1), "CENTER"),
                    ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#D8DEE9")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )

        # Цветовое кодирование баллов
        for i in range(1, 6):  # строки с баллами
            score_cell = (1, i)
            if hasattr(
                report,
                [
                    "technical_skills_score",
                    "experience_relevance_score",
                    "communication_score",
                    "problem_solving_score",
                    "cultural_fit_score",
                ][i - 1],
            ):
                score = getattr(
                    report,
                    [
                        "technical_skills_score",
                        "experience_relevance_score",
                        "communication_score",
                        "problem_solving_score",
                        "cultural_fit_score",
                    ][i - 1],
                )
                if score >= 80:
                    criteria_table.setStyle(
                        TableStyle(
                            [
                                (
                                    "BACKGROUND",
                                    score_cell,
                                    score_cell,
                                    colors.HexColor("#A3BE8C"),
                                )
                            ]
                        )
                    )
                elif score >= 60:
                    criteria_table.setStyle(
                        TableStyle(
                            [
                                (
                                    "BACKGROUND",
                                    score_cell,
                                    score_cell,
                                    colors.HexColor("#EBCB8B"),
                                )
                            ]
                        )
                    )
                else:
                    criteria_table.setStyle(
                        TableStyle(
                            [
                                (
                                    "BACKGROUND",
                                    score_cell,
                                    score_cell,
                                    colors.HexColor("#BF616A"),
                                )
                            ]
                        )
                    )

        story.append(criteria_table)
        story.append(Spacer(1, 20))

        # Сильные и слабые стороны
        if report.strengths or report.weaknesses:
            story.append(Paragraph("Анализ кандидата", self.styles["SectionHeader"]))

            if report.strengths:
                story.append(Paragraph("Сильные стороны:", self.styles["SubHeader"]))
                for strength in report.strengths:
                    story.append(Paragraph(f"• {strength}", self.styles["BodyText"]))
                story.append(Spacer(1, 10))

            if report.weaknesses:
                story.append(
                    Paragraph("Области для развития:", self.styles["SubHeader"])
                )
                for weakness in report.weaknesses:
                    story.append(Paragraph(f"• {weakness}", self.styles["BodyText"]))
                story.append(Spacer(1, 10))

        # Красные флаги
        if report.red_flags:
            story.append(Paragraph("Важные риски:", self.styles["SubHeader"]))
            for red_flag in report.red_flags:
                story.append(
                    Paragraph(
                        f"⚠ {red_flag}",
                        ParagraphStyle(
                            name="RedFlag",
                            parent=self.styles["BodyText"],
                            textColor=colors.HexColor("#BF616A"),
                        ),
                    )
                )
            story.append(Spacer(1, 15))

        # Рекомендации и следующие шаги
        if report.next_steps:
            story.append(Paragraph("Рекомендации:", self.styles["SectionHeader"]))
            story.append(Paragraph(report.next_steps, self.styles["BodyText"]))
            story.append(Spacer(1, 15))

        # Метрики интервью
        if any(
            [
                report.interview_duration_minutes,
                report.dialogue_messages_count,
                report.questions_quality_score,
            ]
        ):
            story.append(Paragraph("Метрики интервью", self.styles["SectionHeader"]))

            metrics = []
            if report.interview_duration_minutes:
                metrics.append(
                    ["Длительность:", f"{report.interview_duration_minutes} мин"]
                )
            if report.dialogue_messages_count:
                metrics.append(
                    ["Сообщений в диалоге:", str(report.dialogue_messages_count)]
                )
            if report.questions_quality_score:
                metrics.append(
                    ["Качество ответов:", f"{report.questions_quality_score:.1f}/10"]
                )

            metrics_table = Table(metrics, colWidths=[2 * inch, 2 * inch])
            metrics_table.setStyle(
                TableStyle(
                    [
                        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 10),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            story.append(metrics_table)

        # Подпись
        story.append(Spacer(1, 30))
        story.append(
            Paragraph(
                f"Отчет сгенерирован автоматически • {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                ParagraphStyle(
                    name="Footer",
                    parent=self.styles["Normal"],
                    fontSize=8,
                    alignment=TA_CENTER,
                    textColor=colors.HexColor("#4C566A"),
                ),
            )
        )

        # Генерируем PDF
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()

    def _format_recommendation(self, recommendation: RecommendationType) -> str:
        """Форматирует рекомендацию для отображения"""
        recommendation_map = {
            RecommendationType.STRONGLY_RECOMMEND: "✅ Настоятельно рекомендуем",
            RecommendationType.RECOMMEND: "👍 Рекомендуем",
            RecommendationType.CONSIDER: "🤔 Рассмотреть кандидатуру",
            RecommendationType.REJECT: "❌ Не рекомендуем",
        }
        return recommendation_map.get(recommendation, str(recommendation))

    async def generate_and_upload_pdf(
        self, report: InterviewReport, candidate_name: str, position: str
    ) -> str | None:
        """
        Генерирует PDF отчет и загружает его в S3

        Args:
            report: Модель отчета из БД
            candidate_name: Имя кандидата
            position: Название позиции

        Returns:
            str | None: URL файла в S3 или None при ошибке
        """
        try:
            # Генерируем PDF
            pdf_bytes = await self.generate_interview_report_pdf(
                report, candidate_name, position
            )

            # Формируем имя файла
            safe_name = "".join(
                c for c in candidate_name if c.isalnum() or c in (" ", "-", "_")
            ).strip()
            safe_name = safe_name.replace(" ", "_")
            filename = f"interview_report_{safe_name}_{report.id}.pdf"

            # Загружаем в S3
            file_url = await s3_service.upload_file(
                file_content=pdf_bytes,
                file_name=filename,
                content_type="application/pdf",
            )

            return file_url

        except Exception as e:
            print(f"Error generating and uploading PDF report: {e}")
            return None


# Экземпляр сервиса
pdf_report_service = PDFReportService()
