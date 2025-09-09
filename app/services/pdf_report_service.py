import io
import os
import shutil
import tempfile
from datetime import datetime
from urllib.parse import quote

import requests
from jinja2 import Template
from playwright.async_api import async_playwright

from app.core.s3 import s3_service
from app.models.interview_report import InterviewReport, RecommendationType


class PDFReportService:
    """Сервис для генерации PDF отчетов по интервью на основе HTML шаблона"""

    def __init__(self):
        self.template_path = "templates/interview_report.html"
        self._setup_fonts()

    def _download_font(self, url: str, dest_path: str) -> str:
        """Скачивает шрифт по URL в dest_path (перезаписывает если нужно)."""
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        try:
            resp = requests.get(url, stream=True, timeout=15)
            resp.raise_for_status()
            with open(dest_path, "wb") as f:
                shutil.copyfileobj(resp.raw, f)
            print(f"[OK] Downloaded font {url} -> {dest_path}")
            return dest_path
        except Exception as e:
            print(f"[ERROR] Failed to download font {url}: {e}")
            raise

    def _register_local_fonts(self, regular_path: str, bold_path: str):
        """Регистрирует шрифты в ReportLab, чтобы xhtml2pdf мог ими пользоваться."""
        try:
            from reportlab.lib.fonts import addMapping
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont

            pdfmetrics.registerFont(TTFont("DejaVuSans", regular_path))
            pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", bold_path))
            # mapping: family, bold(1)/normal(0), italic(1)/normal(0), fontkey
            addMapping("DejaVuSans", 0, 0, "DejaVuSans")
            addMapping("DejaVuSans", 1, 0, "DejaVuSans-Bold")

            self.available_fonts = ["DejaVuSans", "DejaVuSans-Bold"]
            print("[OK] Registered DejaVu fonts in ReportLab")
        except Exception as e:
            print(f"[ERROR] Register fonts failed: {e}")
            self.available_fonts = []

    def _setup_fonts(self):
        """Настройка русских шрифтов для xhtml2pdf"""
        self.available_fonts = []

        try:
            from reportlab.lib.fonts import addMapping
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont

            # Используем скачанные DejaVu шрифты
            fonts_dir = "static/fonts"
            font_paths = [
                (os.path.join(fonts_dir, "DejaVuSans.ttf"), "DejaVu", False, False),
                (os.path.join(fonts_dir, "DejaVuSans-Bold.ttf"), "DejaVu", True, False),
            ]

            for font_path, font_name, is_bold, is_italic in font_paths:
                if os.path.exists(font_path):
                    try:
                        font_key = f"{font_name}"
                        if is_bold:
                            font_key += "-Bold"
                        if is_italic:
                            font_key += "-Italic"

                        # Проверяем, что шрифт можно загрузить
                        test_font = TTFont(font_key, font_path)
                        pdfmetrics.registerFont(test_font)
                        addMapping(font_name, is_bold, is_italic, font_key)

                        self.available_fonts.append(font_key)
                        print(f"[OK] Successfully registered font: {font_key}")

                    except Exception as e:
                        print(f"[ERROR] Failed to register font {font_path}: {e}")
                else:
                    print(f"[ERROR] Font file not found: {font_path}")

        except Exception as e:
            print(f"[ERROR] Font setup failed: {e}")

        print(f"Available fonts: {self.available_fonts}")

    def _get_font_css(self) -> str:
        """Возвращает CSS с подключением локальных шрифтов (скачивает при необходимости)."""
        # paths локальные
        fonts_dir = os.path.abspath("static/fonts").replace("\\", "/")
        regular_local = os.path.join(fonts_dir, "DejaVuSans.ttf").replace("\\", "/")
        bold_local = os.path.join(fonts_dir, "DejaVuSans-Bold.ttf").replace("\\", "/")

        # твои удалённые URL (используй свои)
        remote_regular = (
            "https://d8d88bee-afd2-4266-8332-538389e25f52.selstorage.ru/DejaVuSans.ttf"
        )
        remote_bold = "https://d8d88bee-afd2-4266-8332-538389e25f52.selstorage.ru/DejaVuSans-Bold.ttf"

        # скачиваем если локально нет
        try:
            if not os.path.exists(regular_local) or os.path.getsize(regular_local) == 0:
                self._download_font(remote_regular, regular_local)
            if not os.path.exists(bold_local) or os.path.getsize(bold_local) == 0:
                self._download_font(remote_bold, bold_local)
        except Exception as e:
            print("[WARNING] Failed to ensure local fonts:", e)

        # регистрируем в ReportLab (чтобы гарантировать поддержку кириллицы)
        try:
            self._register_local_fonts(regular_local, bold_local)
        except Exception as e:
            print("[WARNING] Font registration error:", e)

        # используем file:/// абсолютный путь в src и УБИРАЕМ format('...') — это важно
        # url-энкодим путь на случай пробелов
        reg_quoted = quote(regular_local)
        bold_quoted = quote(bold_local)

        font_css = f"""
        <style>
        @font-face {{
            font-family: 'DejaVuSans';
            src: url('file:///{reg_quoted}');
            font-weight: normal;
            font-style: normal;
        }}
        @font-face {{
            font-family: 'DejaVuSans';
            src: url('file:///{bold_quoted}');
            font-weight: bold;
            font-style: normal;
        }}

        /* Применяем семейство — без !important, чтобы не ломать шаблон */
        body, * {{
            font-family: 'DejaVuSans', Arial, sans-serif;
        }}

        @page {{
            size: A4;
            margin: 0.75in;
        }}
        </style>
        """
        return font_css

    def _load_html_template(self) -> str:
        """Загружает HTML шаблон из файла"""
        try:
            with open(self.template_path, encoding="utf-8") as file:
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

    def _format_list_field(self, field_value) -> str:
        """Форматирует поле со списком для отображения"""
        if not field_value:
            return "Не указаны"

        if isinstance(field_value, list):
            return "\n".join([f"• {item}" for item in field_value])
        elif isinstance(field_value, str):
            return field_value
        else:
            return str(field_value)

    def _get_score_class(self, score: int) -> str:
        """Возвращает CSS класс для цвета оценки"""
        if score >= 90:
            return "score-green"  # STRONGLY_RECOMMEND
        elif score >= 75:
            return "score-light-green"  # RECOMMEND
        elif score >= 60:
            return "score-orange"  # CONSIDER
        else:
            return "score-red"  # REJECT

    def _format_recommendation(self, recommendation: RecommendationType) -> tuple:
        """Форматирует рекомендацию для отображения"""
        if recommendation == RecommendationType.STRONGLY_RECOMMEND:
            return ("Настоятельно рекомендуем", "recommend-button")
        elif recommendation == RecommendationType.RECOMMEND:
            return ("Рекомендуем", "recommend-button")
        elif recommendation == RecommendationType.CONSIDER:
            return ("К рассмотрению", "consider-button")
        else:  # REJECT
            return ("Не рекомендуем", "reject-button")

    def link_callback(self, uri, rel):
        """Скачивает удалённый ресурс в temp файл и возвращает путь (для xhtml2pdf)."""
        # remote -> сохранить во временный файл и вернуть путь
        if uri.startswith("http://") or uri.startswith("https://"):
            try:
                r = requests.get(uri, stream=True, timeout=15)
                r.raise_for_status()
                fd, tmp_path = tempfile.mkstemp(suffix=os.path.basename(uri))
                with os.fdopen(fd, "wb") as f:
                    for chunk in r.iter_content(8192):
                        f.write(chunk)
                return tmp_path
            except Exception as e:
                raise Exception(f"Не удалось скачать ресурс {uri}: {e}")
        # file:///path -> без префикса
        if uri.startswith("file:///"):
            return uri[7:]
        # локальные относительные пути
        if os.path.isfile(uri):
            return uri
        # fallback — возвращаем как есть (pisa попробует обработать)
        return uri

    def fetch_resources(self, uri, rel):
        # Разрешаем xhtml2pdf скачивать https
        return self.link_callback(uri, rel)

    async def generate_pdf_report(
        self,
        interview_report: InterviewReport,
        candidate_name: str = None,
        position: str = None,
        resume_file_url: str = None,
    ) -> bytes:
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
            template_data = self._prepare_template_data(
                interview_report,
                candidate_name or "Не указано",
                position or "Не указана",
                resume_file_url,
            )

            # Рендерим HTML с данными
            template = Template(html_template)
            rendered_html = template.render(**template_data)

            # Получаем CSS с проверенными шрифтами
            font_css = self._get_font_css()

            # Вставляем стили
            if "<head>" in rendered_html:
                rendered_html = rendered_html.replace("<head>", f"<head>{font_css}")
            else:
                rendered_html = font_css + rendered_html

            with open("debug.html", "w", encoding="utf-8") as f:
                f.write(rendered_html)

            # Генерируем PDF из debug.html с помощью Playwright
            print("[OK] Using Playwright to generate PDF from debug.html")

            async def generate_pdf():
                async with async_playwright() as p:
                    browser = await p.chromium.launch()
                    page = await browser.new_page()
                    await page.goto(f"file://{os.path.abspath('debug.html')}")
                    await page.wait_for_load_state("networkidle")
                    pdf_bytes = await page.pdf(
                        format="A4",
                        margin={
                            "top": "0.75in",
                            "bottom": "0.75in",
                            "left": "0.75in",
                            "right": "0.75in",
                        },
                        print_background=True,
                    )
                    await browser.close()
                    return pdf_bytes

            pdf_bytes = await generate_pdf()

            return pdf_bytes

        except Exception as e:
            raise Exception(f"Ошибка при генерации PDF: {str(e)}")

    def _prepare_template_data(
        self,
        interview_report: InterviewReport,
        candidate_name: str,
        position: str,
        resume_file_url: str = None,
    ) -> dict:
        """Подготавливает данные для HTML шаблона"""

        # Используем переданные параметры как в старой версии
        resume_url = resume_file_url  # Пока оставим заглушку для ссылки на резюме

        # Форматируем дату интервью
        interview_date = "Не указана"
        if (
            interview_report.interview_session
            and interview_report.interview_session.interview_start_time
        ):
            interview_date = (
                interview_report.interview_session.interview_start_time.strftime(
                    "%d.%m.%Y %H:%M"
                )
            )

        # Общий балл и рекомендация
        overall_score = interview_report.overall_score or 0
        recommendation_text, recommendation_class = self._format_recommendation(
            interview_report.recommendation
        )

        # Сильные стороны и области развития (используем правильные поля модели)
        strengths = (
            self._format_list_field(interview_report.strengths)
            if interview_report.strengths
            else "Не указаны"
        )
        areas_for_development = (
            self._format_list_field(interview_report.weaknesses)
            if interview_report.weaknesses
            else "Не указаны"
        )

        # Детальная оценка - всегда все критерии, как в старой версии
        evaluation_criteria = [
            {
                "name": "Технические навыки",
                "score": interview_report.technical_skills_score or 0,
                "score_class": self._get_score_class(
                    interview_report.technical_skills_score or 0
                ),
                "justification": interview_report.technical_skills_justification or "—",
                "concerns": self._format_concerns_field(
                    interview_report.technical_skills_concerns
                ),
            },
            {
                "name": "Релевантность опыта",
                "score": interview_report.experience_relevance_score or 0,
                "score_class": self._get_score_class(
                    interview_report.experience_relevance_score or 0
                ),
                "justification": interview_report.experience_relevance_justification
                or "—",
                "concerns": self._format_concerns_field(
                    interview_report.experience_relevance_concerns
                ),
            },
            {
                "name": "Коммуникация",
                "score": interview_report.communication_score or 0,
                "score_class": self._get_score_class(
                    interview_report.communication_score or 0
                ),
                "justification": interview_report.communication_justification or "—",
                "concerns": self._format_concerns_field(
                    interview_report.communication_concerns
                ),
            },
            {
                "name": "Решение задач",
                "score": interview_report.problem_solving_score or 0,
                "score_class": self._get_score_class(
                    interview_report.problem_solving_score or 0
                ),
                "justification": interview_report.problem_solving_justification or "—",
                "concerns": self._format_concerns_field(
                    interview_report.problem_solving_concerns
                ),
            },
            {
                "name": "Культурное соответствие",
                "score": interview_report.cultural_fit_score or 0,
                "score_class": self._get_score_class(
                    interview_report.cultural_fit_score or 0
                ),
                "justification": interview_report.cultural_fit_justification or "—",
                "concerns": self._format_concerns_field(
                    interview_report.cultural_fit_concerns
                ),
            },
        ]

        # Красные флаги - используем поле модели напрямую
        red_flags = interview_report.red_flags or []

        # Ссылка на резюме (уже определена выше)

        # ID отчета
        report_id = f"#{interview_report.id}" if interview_report.id else "#0"

        # Дата генерации отчета
        generation_date = datetime.now().strftime("%d.%m.%Y %H:%M")

        return {
            "report_id": report_id,
            "candidate_name": candidate_name,
            "position": position,
            "interview_date": interview_date,
            "overall_score": overall_score,
            "recommendation_text": recommendation_text,
            "recommendation_class": recommendation_class,
            "strengths": strengths,
            "areas_for_development": areas_for_development,
            "evaluation_criteria": evaluation_criteria,
            "red_flags": red_flags,
            "resume_url": resume_url,
            "generation_date": generation_date,
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
                pdf_stream, filename, content_type="application/pdf", public=True
            )

            return file_url

        except Exception as e:
            raise Exception(f"Ошибка при загрузке PDF в S3: {str(e)}")

    async def generate_and_upload_pdf(
        self,
        report: InterviewReport,
        candidate_name: str = None,
        position: str = None,
        resume_file_url: str = None,
    ) -> str:
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
            pdf_bytes = await self.generate_pdf_report(
                report, candidate_name, position, resume_file_url
            )

            # Создаем имя файла - используем переданный параметр как в старой версии
            safe_name = (
                candidate_name
                if candidate_name and candidate_name != "Не указано"
                else "candidate"
            )

            safe_name = "".join(
                c for c in safe_name if c.isalnum() or c in (" ", "-", "_")
            ).strip()
            filename = f"interview_report_{safe_name}_{report.id}.pdf"

            # Загружаем в S3
            pdf_url = await self.upload_pdf_to_s3(pdf_bytes, filename)

            return pdf_url

        except Exception as e:
            raise Exception(f"Ошибка при генерации и загрузке PDF: {str(e)}")


# Экземпляр сервиса
pdf_report_service = PDFReportService()
