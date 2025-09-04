import json
import os
from typing import Any

from celery_worker.celery_app import celery_app
from celery_worker.database import SyncResumeRepository, get_sync_session
from rag.llm.model import ResumeParser
from rag.registry import registry

# Импортируем новые задачи анализа интервью


def generate_interview_plan(
    resume_id: int, combined_data: dict[str, Any]
) -> dict[str, Any]:
    """Генерирует план интервью на основе резюме и вакансии"""
    try:
        # Получаем данные о вакансии из БД
        with get_sync_session() as session:
            repo = SyncResumeRepository(session)
            resume_record = repo.get_by_id(resume_id)

            if not resume_record:
                return None

            # Здесь нужно получить данные вакансии
            # Пока используем заглушку, потом добавим связь с vacancy
            vacancy_data = {
                "title": "Python Developer",
                "requirements": "Python, FastAPI, PostgreSQL, Docker",
                "company_name": "Tech Company",
                "experience_level": "Middle",
            }

        # Генерируем план через LLM
        chat_model = registry.get_chat_model()

        plan_prompt = f"""
        Создай детальный план интервью для кандидата на основе его резюме и требований вакансии.
        
        РЕЗЮМЕ КАНДИДАТА:
        - Имя: {combined_data.get("name", "Не указано")}
        - Навыки: {", ".join(combined_data.get("skills", []))}
        - Опыт: {combined_data.get("total_years", 0)} лет
        - Образование: {combined_data.get("education", "Не указано")}
        
        ВАКАНСИЯ:
        - Позиция: {vacancy_data["title"]}
        - Требования: {vacancy_data["requirements"]}
        - Компания: {vacancy_data["company_name"]}
        - Уровень: {vacancy_data["experience_level"]}
        
        Создай план интервью в формате JSON:
        {{
            "interview_structure": {{
                "duration_minutes": 45,
                "greeting": "Краткое приветствие и знакомство (3 мин)",
                "sections": [
                    {{
                        "name": "Знакомство с кандидатом",
                        "duration_minutes": 5,
                        "questions": ["Расскажи о себе", "Что привлекло в этой позиции?"]
                    }},
                    {{
                        "name": "Технические навыки",
                        "duration_minutes": 20,
                        "questions": ["Опыт с Python", "Работа с базами данных"]
                    }},
                    {{
                        "name": "Опыт и проекты", 
                        "duration_minutes": 15,
                        "questions": ["Расскажи о сложном проекте", "Как решаешь проблемы?"]
                    }},
                    {{
                        "name": "Вопросы кандидата",
                        "duration_minutes": 2,
                        "questions": ["Есть ли вопросы ко мне?"]
                    }}
                ]
            }},
            "focus_areas": ["technical_skills", "problem_solving", "cultural_fit"],
            "key_evaluation_points": [
                "Глубина знаний Python",
                "Опыт командной работы", 
                "Мотивация к изучению нового"
            ],
            "red_flags_to_check": [],
            "personalization_notes": "Кандидат имеет хороший технический опыт"
        }}
        """

        from langchain.schema import HumanMessage, SystemMessage

        messages = [
            SystemMessage(
                content="Ты HR эксперт по планированию интервью. Создавай структурированные планы."
            ),
            HumanMessage(content=plan_prompt),
        ]

        response = chat_model.get_llm().invoke(messages)
        response_text = response.content.strip()

        # Парсим JSON ответ
        if response_text.startswith("{") and response_text.endswith("}"):
            return json.loads(response_text)
        else:
            # Ищем JSON в тексте
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(response_text[start:end])

        return None

    except Exception as e:
        print(f"Ошибка генерации плана интервью: {str(e)}")
        return None


@celery_app.task(bind=True)
def parse_resume_task(self, resume_id: str, file_path: str):
    """
    Асинхронная задача парсинга резюме

    Args:
        resume_id: ID резюме
        file_path: Путь к PDF файлу резюме
    """

    try:
        # Шаг 0: Обновляем статус в БД - начали парсинг
        with get_sync_session() as session:
            repo = SyncResumeRepository(session)
            repo.update_status(int(resume_id), "parsing")

        # Обновляем статус задачи
        self.update_state(
            state="PENDING",
            meta={"status": "Начинаем парсинг резюме...", "progress": 10},
        )

        # Инициализируем модели из registry
        try:
            chat_model = registry.get_chat_model()
            embeddings_model = registry.get_embeddings_model()
            vector_store = registry.get_vector_store()
        except Exception as e:
            # Обновляем статус в БД - ошибка инициализации
            with get_sync_session() as session:
                repo = SyncResumeRepository(session)
                repo.update_status(
                    int(resume_id),
                    "failed",
                    error_message=f"Ошибка инициализации моделей: {str(e)}",
                )
            raise Exception(f"Ошибка инициализации моделей: {str(e)}")

        # Шаг 1: Парсинг резюме
        self.update_state(
            state="PROGRESS",
            meta={"status": "Извлекаем текст из PDF...", "progress": 20},
        )

        parser = ResumeParser(chat_model)

        if not os.path.exists(file_path):
            # Обновляем статус в БД - файл не найден
            with get_sync_session() as session:
                repo = SyncResumeRepository(session)
                repo.update_status(
                    int(resume_id),
                    "failed",
                    error_message=f"Файл не найден: {file_path}",
                )
            raise Exception(f"Файл не найден: {file_path}")

        parsed_resume = parser.parse_resume_from_file(file_path)

        # Получаем оригинальные данные из формы
        with get_sync_session() as session:
            repo = SyncResumeRepository(session)
            resume_record = repo.get_by_id(int(resume_id))
            if not resume_record:
                raise Exception(f"Резюме с ID {resume_id} не найдено в базе данных")

            # Извлекаем нужные данные пока сессия активна
            applicant_name = resume_record.applicant_name
            applicant_email = resume_record.applicant_email
            applicant_phone = resume_record.applicant_phone

        # Создаем комбинированные данные: навыки и опыт из парсинга, контакты из формы
        combined_data = parsed_resume.copy()
        combined_data["name"] = applicant_name
        combined_data["email"] = applicant_email
        combined_data["phone"] = applicant_phone or parsed_resume.get("phone", "")

        # Шаг 2: Векторизация и сохранение в Milvus
        self.update_state(
            state="PENDING",
            meta={"status": "Сохраняем в векторную базу...", "progress": 60},
        )

        vector_store.add_candidate_profile(str(resume_id), combined_data)

        # Шаг 3: Обновляем статус в PostgreSQL - успешно обработано
        self.update_state(
            state="PENDING",
            meta={"status": "Обновляем статус в базе данных...", "progress": 85},
        )

        # Шаг 4: Генерируем план интервью
        self.update_state(
            state="PENDING",
            meta={"status": "Генерируем план интервью...", "progress": 90},
        )

        interview_plan = generate_interview_plan(int(resume_id), combined_data)

        with get_sync_session() as session:
            repo = SyncResumeRepository(session)
            repo.update_status(int(resume_id), "parsed", parsed_data=combined_data)
            # Сохраняем план интервью
            if interview_plan:
                repo.update_interview_plan(int(resume_id), interview_plan)

        # Завершено успешно
        self.update_state(
            state="SUCCESS",
            meta={
                "status": "Резюме успешно обработано и план интервью готов",
                "progress": 100,
                "result": combined_data,
            },
        )

        return {
            "resume_id": resume_id,
            "status": "completed",
            "parsed_data": combined_data,
        }

    except Exception as e:
        # В случае ошибки
        self.update_state(
            state="FAILURE",
            meta={
                "status": f"Ошибка при обработке резюме: {str(e)}",
                "progress": 0,
                "error": str(e),
            },
        )

        # Обновляем статус в БД как failed
        try:
            with get_sync_session() as session:
                repo = SyncResumeRepository(session)
                repo.update_status(int(resume_id), "failed", error_message=str(e))
        except Exception as db_error:
            print(f"Ошибка при обновлении статуса в БД: {str(db_error)}")

        raise


# Функция больше не нужна - используем SyncResumeRepository напрямую


@celery_app.task(bind=True)
def generate_interview_questions_task(self, resume_id: str, job_description: str):
    """
    Генерация персонализированных вопросов для интервью на основе резюме и описания вакансии

    Args:
        resume_id: ID резюме
        job_description: Описание вакансии
    """
    try:
        self.update_state(
            state="PENDING",
            meta={"status": "Начинаем генерацию вопросов...", "progress": 10},
        )

        # Инициализируем модели
        try:
            chat_model = registry.get_chat_model()
            vector_store = registry.get_vector_store()
        except Exception as e:
            raise Exception(f"Ошибка инициализации моделей: {str(e)}")

        # Шаг 1: Получить parsed резюме из базы данных
        self.update_state(
            state="PENDING",
            meta={"status": "Получаем данные резюме...", "progress": 20},
        )

        with get_sync_session() as session:
            repo = SyncResumeRepository(session)
            resume = repo.get_by_id(int(resume_id))

            if not resume:
                raise Exception(f"Резюме с ID {resume_id} не найдено")

            if not resume.parsed_data:
                raise Exception(f"Резюме {resume_id} еще не обработано")

        # Шаг 2: Получить похожие кандидатов из Milvus для анализа
        self.update_state(
            state="PENDING",
            meta={"status": "Анализируем профиль кандидата...", "progress": 40},
        )

        candidate_skills = " ".join(resume.parsed_data.get("skills", []))
        similar_candidates = vector_store.search_similar_candidates(
            candidate_skills, k=3
        )

        # Шаг 3: Сгенерировать персонализированные вопросы через LLM
        self.update_state(
            state="PENDING",
            meta={"status": "Генерируем вопросы для интервью...", "progress": 70},
        )

        questions_prompt = f"""
        Сгенерируй 10 персонализированных вопросов для интервью кандидата на основе его резюме и описания вакансии.
        
        РЕЗЮМЕ КАНДИДАТА:
        Имя: {resume.parsed_data.get("name", "Не указано")}
        Навыки: {", ".join(resume.parsed_data.get("skills", []))}
        Опыт работы: {resume.parsed_data.get("total_years", 0)} лет
        Образование: {resume.parsed_data.get("education", "Не указано")}
        
        ОПИСАНИЕ ВАКАНСИИ:
        {job_description}
        
        ИНСТРУКЦИИ:
        1. Задавай вопросы, которые помогут оценить технические навыки кандидата
        2. Включи вопросы о конкретном опыте работы из резюме
        3. Добавь вопросы на соответствие требованиям вакансии
        4. Включи 2-3 поведенческих вопроса
        5. Верни ответ в JSON формате
        
        Формат ответа:
        {{
          "questions": [
            {{
              "id": 1,
              "category": "technical|experience|behavioral|vacancy_specific",
              "question": "Текст вопроса",
              "reasoning": "Почему этот вопрос важен для данного кандидата"
            }}
          ]
        }}
        """

        from langchain.schema import HumanMessage, SystemMessage

        messages = [
            SystemMessage(
                content="Ты эксперт по проведению технических интервью. Генерируй качественные, персонализированные вопросы."
            ),
            HumanMessage(content=questions_prompt),
        ]

        response = chat_model.get_llm().invoke(messages)

        # Парсим ответ
        import json

        response_text = response.content.strip()

        # Извлекаем JSON из ответа
        if response_text.startswith("{") and response_text.endswith("}"):
            questions_data = json.loads(response_text)
        else:
            # Ищем JSON внутри текста
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            if start != -1 and end > start:
                json_str = response_text[start:end]
                questions_data = json.loads(json_str)
            else:
                raise ValueError("JSON не найден в ответе LLM")

        # Шаг 4: Сохранить вопросы в notes резюме (пока так, потом можно создать отдельную таблицу)
        self.update_state(
            state="PENDING", meta={"status": "Сохраняем вопросы...", "progress": 90}
        )

        with get_sync_session() as session:
            repo = SyncResumeRepository(session)
            resume = repo.get_by_id(int(resume_id))

            if resume:
                # Сохраняем вопросы в notes (временно)
                existing_notes = resume.notes or ""
                interview_questions = json.dumps(
                    questions_data, ensure_ascii=False, indent=2
                )
                resume.notes = (
                    f"{existing_notes}\n\nINTERVIEW QUESTIONS:\n{interview_questions}"
                )
                from datetime import datetime

                resume.updated_at = datetime.utcnow()

                session.add(resume)

        # Завершено успешно
        self.update_state(
            state="SUCCESS",
            meta={
                "status": "Вопросы для интервью успешно сгенерированы",
                "progress": 100,
                "result": questions_data,
            },
        )

        return {
            "resume_id": resume_id,
            "status": "questions_generated",
            "questions": questions_data["questions"],
        }

    except Exception as e:
        # В случае ошибки
        self.update_state(
            state="FAILURE",
            meta={
                "status": f"Ошибка при генерации вопросов: {str(e)}",
                "progress": 0,
                "error": str(e),
            },
        )
        raise Exception(f"Ошибка при генерации вопросов: {str(e)}")
