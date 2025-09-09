from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from rag.settings import settings

# Создаем синхронный engine для Celery (так как Celery работает в отдельных процессах)
sync_engine = create_engine(
    settings.database_url.replace(
        "asyncpg", "psycopg2"
    ),  # Убираем asyncpg для синхронного подключения
    echo=False,
    future=True,
    connect_args={"client_encoding": "utf8"},  # Принудительно UTF-8
)

# Создаем синхронный session maker
SyncSessionLocal = sessionmaker(bind=sync_engine, autocommit=False, autoflush=False)


@contextmanager
def get_sync_session() -> Session:
    """Получить синхронную сессию для использования в Celery tasks"""
    session = SyncSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


class SyncResumeRepository:
    """Синхронный repository для работы с Resume в Celery tasks"""

    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, resume_id: int):
        """Получить резюме по ID"""
        from app.models.resume import Resume

        return self.session.query(Resume).filter(Resume.id == resume_id).first()

    def update_status(
        self,
        resume_id: int,
        status: str,
        parsed_data: dict = None,
        error_message: str = None,
        rejection_reason: str = None,
    ):
        """Обновить статус резюме"""
        from datetime import datetime

        from app.models.resume import Resume, ResumeStatus

        resume = self.session.query(Resume).filter(Resume.id == resume_id).first()

        if resume:
            # Обновляем статус
            if status == "parsing":
                resume.status = ResumeStatus.PARSING
            elif status == "parsed":
                resume.status = ResumeStatus.PARSED
                if parsed_data:
                    resume.parsed_data = parsed_data
            elif status == "failed":
                resume.status = ResumeStatus.PARSE_FAILED
                if error_message:
                    resume.parse_error = error_message
            elif status == "rejected":
                resume.status = ResumeStatus.REJECTED
                if rejection_reason:
                    resume.notes = f"ОТКЛОНЕНО: {rejection_reason}"

            resume.updated_at = datetime.utcnow()
            self.session.add(resume)
            return resume

        return None

    def update_interview_plan(self, resume_id: int, interview_plan: dict):
        """Обновить план интервью"""
        from datetime import datetime

        from app.models.resume import Resume

        resume = self.session.query(Resume).filter(Resume.id == resume_id).first()

        if resume:
            resume.interview_plan = interview_plan
            resume.updated_at = datetime.utcnow()
            self.session.add(resume)
            return resume

        return None

    def _normalize_utf8_dict(self, data):
        """Нормализует UTF-8 в словаре рекурсивно"""
        import json

        # Сериализуем в JSON с ensure_ascii=False, потом парсим обратно
        # Это принудительно конвертирует все unicode escape sequences в нормальные символы
        try:
            json_str = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
            return json.loads(json_str)
        except (TypeError, ValueError):
            # Fallback - рекурсивная обработка
            if isinstance(data, dict):
                return {
                    key: self._normalize_utf8_dict(value) for key, value in data.items()
                }
            elif isinstance(data, list):
                return [self._normalize_utf8_dict(item) for item in data]
            elif isinstance(data, str):
                try:
                    # Пытаемся декодировать unicode escape sequences
                    if "\\u" in data:
                        return data.encode().decode("unicode_escape")
                    return data
                except (UnicodeDecodeError, UnicodeEncodeError):
                    return data
            else:
                return data


class SyncVacancyRepository:
    """Синхронный repository для работы с Vacancy в Celery tasks"""

    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, vacancy_id: int):
        """Получить вакансию по ID"""
        from app.models.vacancy import Vacancy

        return self.session.query(Vacancy).filter(Vacancy.id == vacancy_id).first()

    def create_vacancy(self, vacancy_create):
        """Создать новую вакансию"""
        from datetime import datetime

        from app.models.vacancy import Vacancy

        # Конвертируем VacancyCreate в dict
        if hasattr(vacancy_create, "dict"):
            vacancy_data = vacancy_create.dict()
        elif hasattr(vacancy_create, "model_dump"):
            vacancy_data = vacancy_create.model_dump()
        else:
            vacancy_data = vacancy_create

        # Создаем новую вакансию
        vacancy = Vacancy(
            **vacancy_data, created_at=datetime.utcnow(), updated_at=datetime.utcnow()
        )

        self.session.add(vacancy)
        self.session.flush()  # Получаем ID без коммита
        self.session.refresh(vacancy)  # Обновляем объект из БД

        # Создаем простой объект с нужными данными для возврата
        class VacancyResult:
            def __init__(self, id, title):
                self.id = id
                self.title = title

        return VacancyResult(vacancy.id, vacancy.title)


class SyncInterviewReportRepository:
    """Синхронный repository для работы с InterviewReport в Celery tasks"""

    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, report_id: int):
        """Получить отчет по ID"""
        from app.models.interview_report import InterviewReport

        return (
            self.session.query(InterviewReport)
            .filter(InterviewReport.id == report_id)
            .first()
        )

    def update_pdf_url(self, report_id: int, pdf_url: str) -> bool:
        """Обновить ссылку на PDF отчёта"""
        from datetime import datetime

        from app.models.interview_report import InterviewReport

        try:
            report = (
                self.session.query(InterviewReport)
                .filter(InterviewReport.id == report_id)
                .first()
            )
            if report:
                report.pdf_report_url = pdf_url
                report.updated_at = datetime.utcnow()
                self.session.add(report)
                return True
            return False
        except Exception:
            return False
