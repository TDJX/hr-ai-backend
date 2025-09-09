import asyncio
import json
import logging
from datetime import datetime
from typing import Any

from celery import shared_task

from celery_worker.database import SyncResumeRepository, get_sync_session
from rag.settings import settings

logger = logging.getLogger(__name__)


@shared_task
def generate_interview_report(resume_id: int):
    """
    Комплексная оценка кандидата на основе резюме, вакансии и диалога интервью

    Args:
        resume_id: ID резюме для анализа

    Returns:
        dict: Полный отчет с оценками и рекомендациями
    """
    logger.info(f"[INTERVIEW_ANALYSIS] Starting analysis for resume_id: {resume_id}")

    try:
        with get_sync_session() as db:
            repo = SyncResumeRepository(db)

            # Получаем данные резюме
            resume = repo.get_by_id(resume_id)
            if not resume:
                logger.error(f"[INTERVIEW_ANALYSIS] Resume {resume_id} not found")
                return {"error": "Resume not found"}

            # Получаем данные вакансии (если нет - используем пустые данные)
            vacancy = _get_vacancy_data(db, resume.vacancy_id)
            if not vacancy:
                logger.warning(
                    f"[INTERVIEW_ANALYSIS] Vacancy {resume.vacancy_id} not found, using empty vacancy data"
                )
                vacancy = {
                    "id": resume.vacancy_id,
                    "title": "Неизвестная позиция",
                    "description": "Описание недоступно",
                    "requirements": [],
                    "skills_required": [],
                    "experience_level": "middle",
                }

            # Получаем историю интервью
            interview_session = _get_interview_session(db, resume_id)
            logger.info(
                f"[INTERVIEW_ANALYSIS] Found interview_session: {interview_session is not None}"
            )

            if interview_session:
                logger.info(
                    f"[INTERVIEW_ANALYSIS] Session ID: {interview_session.id}, dialogue_history length: {len(interview_session.dialogue_history) if interview_session.dialogue_history else 0}"
                )
            else:
                logger.warning(
                    f"[INTERVIEW_ANALYSIS] No interview session found for resume_id: {resume_id}"
                )

            # Парсим JSON данные
            parsed_resume = _parse_json_field(resume.parsed_data)
            interview_plan = _parse_json_field(resume.interview_plan)
            # Парсим dialogue_history отдельно (это список, а не словарь)
            dialogue_history = []
            if interview_session and interview_session.dialogue_history:
                if isinstance(interview_session.dialogue_history, list):
                    dialogue_history = interview_session.dialogue_history
                elif isinstance(interview_session.dialogue_history, str):
                    try:
                        dialogue_history = json.loads(
                            interview_session.dialogue_history
                        )
                        if not isinstance(dialogue_history, list):
                            dialogue_history = []
                    except (json.JSONDecodeError, TypeError):
                        dialogue_history = []

            logger.info(
                f"[INTERVIEW_ANALYSIS] Parsed dialogue_history length: {len(dialogue_history)}"
            )

            # Генерируем отчет
            report = _generate_comprehensive_report(
                resume_id=resume_id,
                candidate_name=resume.applicant_name,
                vacancy=vacancy,
                parsed_resume=parsed_resume,
                interview_plan=interview_plan,
                dialogue_history=dialogue_history,
            )

            # Сохраняем отчет в БД
            report_instance = _save_report_to_db(db, resume_id, report)

            # Генерируем и загружаем PDF отчет
            if report_instance:
                asyncio.run(
                    _generate_and_upload_pdf_report(
                        db,
                        report_instance,
                        resume.applicant_name,
                        vacancy.get("title", "Unknown Position"),
                        resume.resume_file_url,
                    )
                )

            logger.info(
                f"[INTERVIEW_ANALYSIS] Analysis completed for resume_id: {resume_id}, score: {report['overall_score']}"
            )
            return report

    except Exception as e:
        logger.error(
            f"[INTERVIEW_ANALYSIS] Error analyzing resume {resume_id}: {str(e)}"
        )
        return {"error": str(e)}


def _get_vacancy_data(db, vacancy_id: int) -> dict | None:
    """Получить данные вакансии"""
    try:
        from app.models.vacancy import Vacancy

        vacancy = db.query(Vacancy).filter(Vacancy.id == vacancy_id).first()
        if vacancy:
            # Парсим key_skills в список, если это строка
            key_skills = []
            if vacancy.key_skills:
                if isinstance(vacancy.key_skills, str):
                    # Разделяем по запятым и очищаем от пробелов
                    key_skills = [
                        skill.strip()
                        for skill in vacancy.key_skills.split(",")
                        if skill.strip()
                    ]
                elif isinstance(vacancy.key_skills, list):
                    key_skills = vacancy.key_skills

            # Маппинг Experience enum в строку уровня опыта
            experience_mapping = {
                "noExperience": "junior",
                "between1And3": "junior",
                "between3And6": "middle",
                "moreThan6": "senior",
            }
            experience_level = experience_mapping.get(vacancy.experience, "middle")

            return {
                "id": vacancy.id,
                "title": vacancy.title,
                "description": vacancy.description,
                "requirements": [vacancy.description]
                if vacancy.description
                else [],  # Используем описание как требования
                "skills_required": key_skills,
                "experience_level": experience_level,
                "employment_type": vacancy.employment_type,
                "salary_range": f"{vacancy.salary_from or 0}-{vacancy.salary_to or 0}"
                if vacancy.salary_from or vacancy.salary_to
                else None,
            }
        return None
    except Exception as e:
        logger.error(f"Error getting vacancy data: {e}")
        return None


def _get_interview_session(db, resume_id: int):
    """Получить сессию интервью"""
    try:
        from app.models.interview import InterviewSession

        logger.info(
            f"[GET_SESSION] Looking for interview session with resume_id: {resume_id}"
        )

        session = (
            db.query(InterviewSession)
            .filter(InterviewSession.resume_id == resume_id)
            .first()
        )

        if session:
            logger.info(
                f"[GET_SESSION] Found session {session.id} for resume {resume_id}"
            )
            logger.info(f"[GET_SESSION] Session status: {session.status}")
            logger.info(
                f"[GET_SESSION] Dialogue history type: {type(session.dialogue_history)}"
            )
            if session.dialogue_history:
                logger.info(
                    f"[GET_SESSION] Raw dialogue_history preview: {str(session.dialogue_history)[:200]}..."
                )
        else:
            logger.warning(f"[GET_SESSION] No session found for resume_id: {resume_id}")

        return session

    except Exception as e:
        logger.error(f"Error getting interview session: {e}")
        return None


def _parse_json_field(field_data) -> dict:
    """Безопасный парсинг JSON поля"""
    if field_data is None:
        return {}
    if isinstance(field_data, dict):
        return field_data
    if isinstance(field_data, str):
        try:
            return json.loads(field_data)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _generate_comprehensive_report(
    resume_id: int,
    candidate_name: str,
    vacancy: dict,
    parsed_resume: dict,
    interview_plan: dict,
    dialogue_history: list[dict],
) -> dict[str, Any]:
    """
    Генерирует комплексный отчет о кандидате с использованием LLM
    """

    # Подготавливаем контекст для анализа
    context = _prepare_analysis_context(
        vacancy=vacancy,
        parsed_resume=parsed_resume,
        interview_plan=interview_plan,
        dialogue_history=dialogue_history,
    )

    # Генерируем оценку через OpenAI
    evaluation = _call_openai_for_evaluation(context)

    # Формируем финальный отчет
    report = {
        "resume_id": resume_id,
        "candidate_name": candidate_name,
        "position": vacancy.get("title", "Unknown Position"),
        "interview_date": datetime.utcnow().isoformat(),
        "analysis_context": {
            "has_parsed_resume": bool(parsed_resume),
            "has_interview_plan": bool(interview_plan),
            "dialogue_messages_count": len(dialogue_history),
            "vacancy_requirements_count": len(vacancy.get("requirements", [])),
        },
    }

    # Добавляем результаты оценки
    if evaluation:
        # Убеждаемся, что есть overall_score
        if "overall_score" not in evaluation:
            evaluation["overall_score"] = _calculate_overall_score(evaluation)

        report.update(evaluation)
    else:
        # Fallback оценка, если LLM не сработал
        report.update(
            _generate_fallback_evaluation(parsed_resume, vacancy, dialogue_history)
        )

    return report


def _calculate_overall_score(evaluation: dict) -> int:
    """Вычисляет общий балл как среднее арифметическое всех критериев"""
    try:
        scores = evaluation.get("scores", {})
        if not scores:
            return 50  # Default score

        total_score = 0
        count = 0

        for criterion_name, criterion_data in scores.items():
            if isinstance(criterion_data, dict) and "score" in criterion_data:
                total_score += criterion_data["score"]
                count += 1

        if count == 0:
            return 50  # Default if no valid scores

        overall = int(total_score / count)
        return max(0, min(100, overall))  # Ensure 0-100 range

    except Exception:
        return 50  # Safe fallback


def _prepare_analysis_context(
    vacancy: dict,
    parsed_resume: dict,
    interview_plan: dict,
    dialogue_history: list[dict],
) -> str:
    """Подготавливает контекст для анализа LLM"""

    # Собираем диалог интервью
    dialogue_text = ""
    if dialogue_history:
        dialogue_messages = []
        for msg in dialogue_history[-20:]:  # Последние 20 сообщений
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            dialogue_messages.append(f"{role.upper()}: {content}")
        dialogue_text = "\n".join(dialogue_messages)

    # Формируем контекст
    context = f"""
ВАКАНСИЯ:
- Позиция: {vacancy.get("title", "Не указана")}
- Описание: {vacancy.get("description", "Не указано")[:500]}
- Требования: {", ".join(vacancy.get("requirements", []))}
- Требуемые навыки: {", ".join(vacancy.get("skills_required", []))}
- Уровень опыта: {vacancy.get("experience_level", "middle")}

РЕЗЮМЕ КАНДИДАТА:
- Имя: {parsed_resume.get("name", "Не указано")}
- Опыт работы: {parsed_resume.get("total_years", "Не указано")} лет
- Навыки: {", ".join(parsed_resume.get("skills", []))}
- Образование: {parsed_resume.get("education", "Не указано")}
- Предыдущие позиции: {"; ".join([pos.get("title", "") + " в " + pos.get("company", "") for pos in parsed_resume.get("work_experience", [])])}

ПЛАН СОБЕСЕДОВАНИЯ:
{json.dumps(interview_plan, ensure_ascii=False, indent=2) if interview_plan else "План интервью не найден"}

ДИАЛОГ СОБЕСЕДОВАНИЯ:
{dialogue_text if dialogue_text else "Диалог интервью не найден или пуст"}
"""

    return context


def _call_openai_for_evaluation(context: str) -> dict | None:
    """Вызывает OpenAI для генерации оценки"""

    if not settings.openai_api_key:
        logger.warning("OpenAI API key not configured, skipping LLM evaluation")
        return None

    try:
        import openai

        openai.api_key = settings.openai_api_key

        evaluation_prompt = f"""
{context}

ЗАДАЧА:
Проанализируй ДИАЛОГ с кандидатом. Если кандидат ответил на вопросы и подтвердил знания из резюме, то только тогда можно считать его навыки резюме подтвержденными
и можно оценивать их соответствие вакансионным требованиям. Если клиент уклонялся от вопросов или закончил интервью раньше (или диалог выглядит неполным исходя из плана, хотя интервьюер адаптирует план и сторого ему не следует),
чем это сделал сам интервьюер, то навыки не считаются подтвержденными и по ним нельзя оценивать кандидата

Дай оценку по критериям (0-100):
1. technical_skills: Соответствие диалога (и резюме если диалог подтверждает) техническим требованиям вакансии
2. experience_relevance: Релевантность опыта судя по диалогу (и резюме если диалог подтверждает)
3. communication: Коммуникативные навыки на основе диалога
4. problem_solving: Навыки решения задач на основе диалога
5. cultural_fit: Соответствие корпоративной культуре

Для каждого критерия:
- score: оценка 0-100
- justification: обоснование с примерами из резюме/интервью
- concerns: возможные риски

Дай итоговую рекомендацию:
- strongly_recommend (90-100)
- recommend (70-89) 
- consider (50-69)
- reject (0-49)

Вычисли ОБЩИЙ БАЛЛ (overall_score) от 0 до 100 как среднее арифметическое всех 5 критериев.

И топ 3 сильные/слабые стороны.

И red_flags (если есть): расхождение в стаже и опыте резюме и собеседования, шаблонные ответы, уклонение от вопросов

ОТВЕТЬ СТРОГО В JSON ФОРМАТЕ с обязательными полями:
- scores: объект с 5 критериями, каждый содержит score, justification, concerns
- overall_score: число от 0 до 100 (среднее арифметическое всех scores)
- recommendation: одно из 4 значений выше
- strengths: массив из 3 сильных сторон
- weaknesses: массив из 3 слабых сторон
- red_flags: массив из красных флагов (если есть)
"""

        response = openai.chat.completions.create(
            model="gpt-5-mini",
            messages=[{"role": "user", "content": evaluation_prompt}],
            response_format={"type": "json_object"},
        )

        evaluation = json.loads(response.choices[0].message.content)
        logger.info("[INTERVIEW_ANALYSIS] OpenAI evaluation completed")
        return evaluation

    except Exception as e:
        logger.error(f"[INTERVIEW_ANALYSIS] Error calling OpenAI: {str(e)}")
        return None


def _generate_fallback_evaluation(
    parsed_resume: dict, vacancy: dict, dialogue_history: list[dict]
) -> dict[str, Any]:
    """Генерирует базовую оценку без LLM"""

    # Простая эвристическая оценка
    technical_score = _calculate_technical_match(parsed_resume, vacancy)
    experience_score = _calculate_experience_score(parsed_resume, vacancy)
    communication_score = 70  # Средняя оценка, если нет диалога

    if dialogue_history:
        communication_score = min(
            90, 50 + len(dialogue_history) * 2
        )  # Больше диалога = лучше коммуникация

    overall_score = (technical_score + experience_score + communication_score) // 3

    # Определяем рекомендацию
    if overall_score >= 90:
        recommendation = "strongly_recommend"
    elif overall_score >= 70:
        recommendation = "recommend"
    elif overall_score >= 50:
        recommendation = "consider"
    else:
        recommendation = "reject"

    return {
        "scores": {
            "technical_skills": {
                "score": technical_score,
                "justification": f"Соответствие по навыкам: {technical_score}%",
                "concerns": "Автоматическая оценка без анализа LLM",
            },
            "experience_relevance": {
                "score": experience_score,
                "justification": f"Опыт работы: {parsed_resume.get('total_years', 0)} лет",
                "concerns": "Требуется ручная проверка релевантности опыта",
            },
            "communication": {
                "score": communication_score,
                "justification": f"Активность в диалоге: {len(dialogue_history)} сообщений",
                "concerns": "Оценка основана на количестве сообщений",
            },
            "problem_solving": {
                "score": 60,
                "justification": "Средняя оценка (нет данных для анализа)",
                "concerns": "Требуется техническое интервью",
            },
            "cultural_fit": {
                "score": 65,
                "justification": "Средняя оценка (нет данных для анализа)",
                "concerns": "Требуется личная встреча с командой",
            },
        },
        "overall_score": overall_score,
        "recommendation": recommendation,
        "strengths": [
            f"Опыт работы: {parsed_resume.get('total_years', 0)} лет",
            f"Технические навыки: {len(parsed_resume.get('skills', []))} навыков",
            f"Участие в интервью: {len(dialogue_history)} сообщений",
        ],
        "weaknesses": [
            "Автоматическая оценка без LLM анализа",
            "Требуется дополнительное техническое интервью",
            "Нет глубокого анализа ответов на вопросы",
        ],
        "red_flags": [],
        "next_steps": "Рекомендуется провести техническое интервью с тимлидом для более точной оценки.",
        "analysis_method": "fallback_heuristic",
    }


def _calculate_technical_match(parsed_resume: dict, vacancy: dict) -> int:
    """Вычисляет соответствие технических навыков"""

    resume_skills = set([skill.lower() for skill in parsed_resume.get("skills", [])])
    required_skills = set(
        [skill.lower() for skill in vacancy.get("skills_required", [])]
    )

    if not required_skills:
        return 70  # Если требования не указаны

    matching_skills = resume_skills.intersection(required_skills)
    match_percentage = (len(matching_skills) / len(required_skills)) * 100

    return min(100, int(match_percentage))


def _calculate_experience_score(parsed_resume: dict, vacancy: dict) -> int:
    """Вычисляет оценку релевантности опыта"""

    years_experience = parsed_resume.get("total_years", 0)
    required_level = vacancy.get("experience_level", "middle")

    # Маппинг уровней на годы опыта
    level_mapping = {
        "junior": (0, 2),
        "middle": (2, 5),
        "senior": (5, 10),
        "lead": (8, 15),
    }

    min_years, max_years = level_mapping.get(required_level, (2, 5))

    if years_experience < min_years:
        # Недостаток опыта
        return max(30, int(70 * (years_experience / min_years)))
    elif years_experience > max_years:
        # Переквалификация
        return max(60, int(90 - (years_experience - max_years) * 5))
    else:
        # Подходящий опыт
        return 90


def _save_report_to_db(db, resume_id: int, report: dict):
    """Сохраняет отчет в базу данных в таблицу interview_reports

    Returns:
        InterviewReport | None: Созданный или обновленный экземпляр отчета
    """

    try:
        from app.models.interview import InterviewSession
        from app.models.interview_report import InterviewReport

        # Находим сессию интервью по resume_id
        interview_session = (
            db.query(InterviewSession)
            .filter(InterviewSession.resume_id == resume_id)
            .first()
        )

        if not interview_session:
            logger.warning(
                f"[INTERVIEW_ANALYSIS] No interview session found for resume_id: {resume_id}"
            )
            return None

        # Проверяем, есть ли уже отчет для этой сессии
        existing_report = (
            db.query(InterviewReport)
            .filter(InterviewReport.interview_session_id == interview_session.id)
            .first()
        )

        if existing_report:
            logger.info(
                f"[INTERVIEW_ANALYSIS] Updating existing report for session: {interview_session.id}"
            )
            # Обновляем существующий отчет
            _update_report_from_dict(existing_report, report)
            existing_report.updated_at = datetime.utcnow()
            db.add(existing_report)
            db.commit()
            db.refresh(existing_report)
            return existing_report
        else:
            logger.info(
                f"[INTERVIEW_ANALYSIS] Creating new report for session: {interview_session.id}"
            )
            # Создаем новый отчет
            new_report = _create_report_from_dict(interview_session.id, report)
            db.add(new_report)
            db.commit()
            db.refresh(new_report)
            return new_report

    except Exception as e:
        logger.error(f"[INTERVIEW_ANALYSIS] Error saving report: {str(e)}")
        return None


async def _generate_and_upload_pdf_report(
    db,
    report_instance: "InterviewReport",
    candidate_name: str,
    position: str,
    resume_file_url: str = None,
):
    """Генерирует PDF отчет и загружает его в S3"""
    try:

        from app.services.pdf_report_service import pdf_report_service

        logger.info(
            f"[PDF_GENERATION] Starting PDF generation for report ID: {report_instance.id}"
        )

        # Генерируем и загружаем PDF - используем переданные параметры как в старой версии
        pdf_url = await pdf_report_service.generate_and_upload_pdf(
            report=report_instance,
            candidate_name=candidate_name,
            position=position,
            resume_file_url=resume_file_url,
        )

        if pdf_url:
            # Сохраняем URL в базу данных
            report_instance.pdf_report_url = pdf_url
            db.add(report_instance)
            db.commit()
            logger.info(
                f"[PDF_GENERATION] PDF generated and uploaded successfully: {pdf_url}"
            )
        else:
            logger.error(
                f"[PDF_GENERATION] Failed to generate or upload PDF for report ID: {report_instance.id}"
            )

    except Exception as e:
        logger.error(f"[PDF_GENERATION] Error generating PDF report: {str(e)}")


def _format_concerns_field(concerns_data) -> str:
    """Форматирует поле concerns для сохранения как строку"""
    if not concerns_data:
        return ""

    if isinstance(concerns_data, list):
        # Если это массив, объединяем элементы через запятую с переносом строки
        return "; ".join(concerns_data)
    elif isinstance(concerns_data, str):
        return concerns_data
    else:
        return str(concerns_data)


def _create_report_from_dict(
    interview_session_id: int, report: dict
) -> "InterviewReport":
    """Создает объект InterviewReport из словаря отчета"""
    from app.models.interview_report import InterviewReport, RecommendationType

    # Извлекаем баллы по критериям
    scores = report.get("scores", {})

    return InterviewReport(
        interview_session_id=interview_session_id,
        # Основные критерии оценки
        technical_skills_score=scores.get("technical_skills", {}).get("score", 0),
        technical_skills_justification=scores.get("technical_skills", {}).get(
            "justification", ""
        ),
        technical_skills_concerns=_format_concerns_field(
            scores.get("technical_skills", {}).get("concerns", "")
        ),
        experience_relevance_score=scores.get("experience_relevance", {}).get(
            "score", 0
        ),
        experience_relevance_justification=scores.get("experience_relevance", {}).get(
            "justification", ""
        ),
        experience_relevance_concerns=_format_concerns_field(
            scores.get("experience_relevance", {}).get("concerns", "")
        ),
        communication_score=scores.get("communication", {}).get("score", 0),
        communication_justification=scores.get("communication", {}).get(
            "justification", ""
        ),
        communication_concerns=_format_concerns_field(
            scores.get("communication", {}).get("concerns", "")
        ),
        problem_solving_score=scores.get("problem_solving", {}).get("score", 0),
        problem_solving_justification=scores.get("problem_solving", {}).get(
            "justification", ""
        ),
        problem_solving_concerns=_format_concerns_field(
            scores.get("problem_solving", {}).get("concerns", "")
        ),
        cultural_fit_score=scores.get("cultural_fit", {}).get("score", 0),
        cultural_fit_justification=scores.get("cultural_fit", {}).get(
            "justification", ""
        ),
        cultural_fit_concerns=_format_concerns_field(
            scores.get("cultural_fit", {}).get("concerns", "")
        ),
        # Агрегированные поля
        overall_score=report.get("overall_score", 0),
        recommendation=RecommendationType(report.get("recommendation", "reject")),
        # Дополнительные поля
        strengths=report.get("strengths", []),
        weaknesses=report.get("weaknesses", []),
        red_flags=report.get("red_flags", []),
        # Метрики интервью
        dialogue_messages_count=report.get("analysis_context", {}).get(
            "dialogue_messages_count", 0
        ),
        # Дополнительная информация
        next_steps=report.get("next_steps", ""),
        questions_analysis=report.get("questions_analysis", []),
        # Метаданные анализа
        analysis_method=report.get("analysis_method", "openai_gpt4"),
    )


def _update_report_from_dict(existing_report, report: dict):
    """Обновляет существующий отчет данными из словаря"""
    from app.models.interview_report import RecommendationType

    scores = report.get("scores", {})

    # Основные критерии оценки
    if "technical_skills" in scores:
        existing_report.technical_skills_score = scores["technical_skills"].get(
            "score", 0
        )
        existing_report.technical_skills_justification = scores["technical_skills"].get(
            "justification", ""
        )
        existing_report.technical_skills_concerns = _format_concerns_field(
            scores["technical_skills"].get("concerns", "")
        )

    if "experience_relevance" in scores:
        existing_report.experience_relevance_score = scores["experience_relevance"].get(
            "score", 0
        )
        existing_report.experience_relevance_justification = scores[
            "experience_relevance"
        ].get("justification", "")
        existing_report.experience_relevance_concerns = _format_concerns_field(
            scores["experience_relevance"].get("concerns", "")
        )

    if "communication" in scores:
        existing_report.communication_score = scores["communication"].get("score", 0)
        existing_report.communication_justification = scores["communication"].get(
            "justification", ""
        )
        existing_report.communication_concerns = _format_concerns_field(
            scores["communication"].get("concerns", "")
        )

    if "problem_solving" in scores:
        existing_report.problem_solving_score = scores["problem_solving"].get(
            "score", 0
        )
        existing_report.problem_solving_justification = scores["problem_solving"].get(
            "justification", ""
        )
        existing_report.problem_solving_concerns = _format_concerns_field(
            scores["problem_solving"].get("concerns", "")
        )

    if "cultural_fit" in scores:
        existing_report.cultural_fit_score = scores["cultural_fit"].get("score", 0)
        existing_report.cultural_fit_justification = scores["cultural_fit"].get(
            "justification", ""
        )
        existing_report.cultural_fit_concerns = _format_concerns_field(
            scores["cultural_fit"].get("concerns", "")
        )

    # Агрегированные поля
    if "overall_score" in report:
        existing_report.overall_score = report["overall_score"]

    if "recommendation" in report:
        existing_report.recommendation = RecommendationType(report["recommendation"])

    # Дополнительные поля
    if "strengths" in report:
        existing_report.strengths = report["strengths"]

    if "weaknesses" in report:
        existing_report.weaknesses = report["weaknesses"]

    if "red_flags" in report:
        existing_report.red_flags = report["red_flags"]

    # Метрики интервью
    if "analysis_context" in report:
        existing_report.dialogue_messages_count = report["analysis_context"].get(
            "dialogue_messages_count", 0
        )

    # Дополнительная информация
    if "next_steps" in report:
        existing_report.next_steps = report["next_steps"]

    if "questions_analysis" in report:
        existing_report.questions_analysis = report["questions_analysis"]

    # Метаданные анализа
    if "analysis_method" in report:
        existing_report.analysis_method = report["analysis_method"]


# Дополнительная задача для массового анализа
@shared_task
def analyze_multiple_candidates(resume_ids: list[int]):
    """
    Анализирует несколько кандидатов и возвращает их рейтинг

    Args:
        resume_ids: Список ID резюме для анализа

    Returns:
        List[Dict]: Список кандидатов с оценками, отсортированный по рейтингу
    """
    logger.info(f"[MASS_ANALYSIS] Starting analysis for {len(resume_ids)} candidates")

    results = []

    for resume_id in resume_ids:
        try:
            result = generate_interview_report(resume_id)
            if "error" not in result:
                results.append(
                    {
                        "resume_id": resume_id,
                        "candidate_name": result.get("candidate_name", "Unknown"),
                        "overall_score": result.get("overall_score", 0),
                        "recommendation": result.get("recommendation", "reject"),
                        "position": result.get("position", "Unknown"),
                    }
                )
        except Exception as e:
            logger.error(
                f"[MASS_ANALYSIS] Error analyzing resume {resume_id}: {str(e)}"
            )

    # Сортируем по общему баллу
    results.sort(key=lambda x: x["overall_score"], reverse=True)

    logger.info(f"[MASS_ANALYSIS] Completed analysis for {len(results)} candidates")
    return results
