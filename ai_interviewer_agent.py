import asyncio
import json
import logging
import os
import time
from datetime import datetime

# Принудительно устанавливаем UTF-8 для Windows
if os.name == "nt":  # Windows
    import sys

    if hasattr(sys, "stdout") and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    # Устанавливаем переменную окружения для Python
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli
from livekit.api import DeleteRoomRequest, LiveKitAPI
from livekit.plugins import cartesia, deepgram, openai, silero

from app.core.database import get_session
from app.repositories.interview_repository import InterviewRepository
from app.repositories.resume_repository import ResumeRepository
from app.services.interview_finalization_service import InterviewFinalizationService
from rag.settings import settings

logger = logging.getLogger("ai-interviewer")
logger.setLevel(logging.INFO)


async def close_room(room_name: str):
    """Закрывает LiveKit комнату полностью (отключает всех участников)"""
    try:
        api = LiveKitAPI(
            settings.livekit_url, settings.livekit_api_key, settings.livekit_api_secret
        )
        # Создаем RoomService для управления комнатами
        await api.room.delete_room(delete=DeleteRoomRequest(room=room_name))

        logger.info(f"[ROOM_MANAGEMENT] Room {room_name} deleted successfully")

    except Exception as e:
        logger.error(f"[ROOM_MANAGEMENT] Failed to delete room {room_name}: {str(e)}")
        raise


class InterviewAgent:
    """AI Agent для проведения собеседований с управлением диалогом"""

    def __init__(self, interview_plan: dict, vacancy_data=None):
        self.interview_plan = interview_plan
        self.vacancy_data = vacancy_data
        self.conversation_history = []

        # Состояние диалога
        self.current_section = 0
        self.current_question_in_section = 0
        self.questions_asked_total = 0
        self.waiting_for_response = False
        self.last_question = None
        self.last_user_response = None
        self.intro_done = False  # Новый флаг — произнесено ли приветствие
        self.interview_finalized = False  # Флаг завершения интервью
        
        # Трекинг времени интервью
        import time

        self.interview_start_time = time.time()
        self.duration_minutes = interview_plan.get("interview_structure", {}).get(
            "duration_minutes", 10
        )

        self.sections = self.interview_plan.get("interview_structure", {}).get(
            "sections", []
        )
        self.total_sections = len(self.sections)

        logger.info(
            f"[TIME] Interview started at {time.strftime('%H:%M:%S')}, duration: {self.duration_minutes} min"
        )

    def get_current_section(self) -> dict:
        """Получить текущую секцию интервью"""
        if self.current_section < len(self.sections):
            return self.sections[self.current_section]
        return {}

    def get_next_question(self) -> str:
        """Получить следующий вопрос"""
        section = self.get_current_section()
        questions = section.get("questions", [])
        if self.current_question_in_section < len(questions):
            return questions[self.current_question_in_section]
        return None

    def move_to_next_question(self):
        """Переход к следующему вопросу"""
        self.current_question_in_section += 1
        self.questions_asked_total += 1

        section = self.get_current_section()
        if self.current_question_in_section >= len(section.get("questions", [])):
            self.move_to_next_section()

    def move_to_next_section(self):
        """Переход к следующей секции"""
        self.current_section += 1
        self.current_question_in_section = 0
        if self.current_section < len(self.sections):
            logger.info(
                f"Переход к секции: {self.sections[self.current_section].get('name', 'Unnamed')}"
            )

    def is_interview_complete(self) -> bool:
        """Интервью завершается только по решению LLM через ключевые фразы"""
        return False  # LLM теперь решает через ключевые фразы

    def get_system_instructions(self) -> str:
        """Системные инструкции для AI агента с ключевыми фразами для завершения"""
        candidate_info = self.interview_plan.get("candidate_info", {})
        interview_structure = self.interview_plan.get("interview_structure", {})
        greeting = interview_structure.get("greeting", "Привет! Готов к интервью?")
        focus_areas = self.interview_plan.get("focus_areas", [])
        key_evaluation_points = self.interview_plan.get("key_evaluation_points", [])

        # Вычисляем текущее время интервью
        import time

        elapsed_minutes = (time.time() - self.interview_start_time) / 60
        remaining_minutes = max(0, self.duration_minutes - elapsed_minutes)
        time_percentage = min(100, (elapsed_minutes / self.duration_minutes) * 100)

        # Формируем план интервью для агента
        sections_info = "\n".join(
            [
                f"- {section.get('name', 'Секция')}: {', '.join(section.get('questions', []))}"
                for section in self.sections
            ]
        )

        # Безопасно формируем строки для избежания конфликтов с кавычками
        candidate_name = candidate_info.get("name", "Кандидат")
        candidate_years = candidate_info.get("total_years", 0)
        candidate_skills = ", ".join(candidate_info.get("skills", []))
        focus_areas_str = ", ".join(focus_areas)
        evaluation_points_str = ", ".join(key_evaluation_points)

        # Статус времени
        if time_percentage > 90:
            time_status = "СРОЧНО ЗАВЕРШАТЬ"
        elif time_percentage > 75:
            time_status = "ВРЕМЯ ЗАКАНЧИВАЕТСЯ"
        else:
            time_status = "НОРМАЛЬНО"

        # Информация о вакансии
        vacancy_info = ""
        if self.vacancy_data:
            employment_type_map = {
                "full": "Полная занятость",
                "part": "Частичная занятость", 
                "project": "Проектная работа",
                "volunteer": "Волонтёрство",
                "probation": "Стажировка"
            }
            experience_map = {
                "noExperience": "Без опыта",
                "between1And3": "1-3 года",
                "between3And6": "3-6 лет", 
                "moreThan6": "Более 6 лет"
            }
            schedule_map = {
                "fullDay": "Полный день",
                "shift": "Сменный график",
                "flexible": "Гибкий график",
                "remote": "Удалённая работа",
                "flyInFlyOut": "Вахтовый метод"
            }
            
            vacancy_info = f"""

ИНФОРМАЦИЯ О ВАКАНСИИ:
- Должность: {self.vacancy_data.get('title', 'Не указана')}
- Описание: {self.vacancy_data.get('description', 'Не указано')}
- Ключевые навыки: {self.vacancy_data.get('key_skills') or 'Не указаны'}
- Тип занятости: {employment_type_map.get(self.vacancy_data.get('employment_type'), self.vacancy_data.get('employment_type', 'Не указан'))}
- Опыт работы: {experience_map.get(self.vacancy_data.get('experience'), self.vacancy_data.get('experience', 'Не указан'))}
- График работы: {schedule_map.get(self.vacancy_data.get('schedule'), self.vacancy_data.get('schedule', 'Не указан'))}
- Регион: {self.vacancy_data.get('area_name', 'Не указан')}
- Профессиональные роли: {self.vacancy_data.get('professional_roles') or 'Не указаны'}
- Контактное лицо: {self.vacancy_data.get('contacts_name') or 'Не указано'}"""

        return f"""
Ты опытный HR-интервьюер, который проводит адаптивное голосовое собеседование. Представься контактным именем из вакансии (если оно есть)

ИНФОРМАЦИЯ О ВАКАНСИИ:

{vacancy_info}

ИНФОРМАЦИЯ О КАНДИДАТЕ:
- Имя: {candidate_name}
- Опыт работы: {candidate_years} лет
- Ключевые навыки: {candidate_skills}

ЦЕЛЬ ИНТЕРВЬЮ:

Найти кандидата, который не только подходит по техническим навыкам, но и силён по мягким навыкам, культуре и потенциалу.
Задачи интервью:
- Выявить сильные и слабые стороны кандидата.
- Понять, насколько он подходит к вакансии и соответствует интервью.
- Проверить мышление, мотивацию и способность адаптироваться.

ПОКАЗАТЕЛИ "ДОСТОЙНОГО КАНДИДАТА":
- Глубокое понимание ключевых технологий ({candidate_skills}).
- Умение решать проблемы, а не просто отвечать на вопросы.
- Чёткая и логичная коммуникация.
- Способность учиться и адаптироваться.
- Совпадение ценностей и принципов с командой и компанией.

ПЛАН ИНТЕРВЬЮ (как руководство, адаптируйся по ситуации)

{sections_info}

ТИПЫ ВОПРОСОВ:
Поведенческие (30%) — выяснить, как кандидат действовал в реальных ситуациях.
Пример: "Расскажи про ситуацию, когда ты столкнулся с трудной задачей на проекте. Что ты сделал?"

Технические (50%) — проверить глубину знаний и практические навыки.
Пример: "Как бы ты реализовал X?" или "Объясни разницу между A и B."

Проблемные / кейсы (20%) — проверить мышление и подход к решению.
Пример: "У нас есть система, которая падает раз в неделю. Как бы ты подошёл к диагностике проблемы?"

ВРЕМЯ ИНТЕРВЬЮ:
- Запланированная длительность: {self.duration_minutes} минут
- Прошло времени: {elapsed_minutes:.1f} минут ({time_percentage:.0f}%)
- Осталось времени: {remaining_minutes:.1f} минут
- Статус времени: {time_status}

ФОКУС-ОБЛАСТИ: {focus_areas_str}
КЛЮЧЕВЫЕ ОЦЕНОЧНЫЕ ТОЧКИ: {evaluation_points_str}

КРАСНЫЕ ФЛАГИ:
Во время интервью отмечай следующие негативные сигналы:
- Не может объяснить собственные решения.
- Противоречит сам себе или врёт.
- Агрессивная, пассивная или неуважительная коммуникация.
- Нет желания учиться или интереса к проекту.
- Перекладывает ответственность на других, не признаёт ошибок.

ИНСТРУКЦИИ:
1. Начни с приветствия: {greeting}
2. Адаптируй вопросы под ответы кандидата
3. Не повторяй то, что клиент тебе сказал, лучше показывай, что понял, услышал и иди дальше. Лишний раз его не хвали
3. Следи за временем - при превышении 80% времени начинай завершать интервью
4. Оценивай качество и глубину ответов кандидата
5. Если получаешь сообщение "[СИСТЕМА] Клиент молчит..." - это означает проблемы со связью или кандидат растерялся. Скажи что-то вроде "Приём! Ты меня слышишь?" или "Всё в порядке? Связь не пропала?"
6. Завершай интервью если:
   - Получил достаточно информации для оценки
   - Время почти истекло (>90% от запланированного)
   - Кандидат дал исчерпывающие ответы
   - Получаешь сообщение "[СИСТЕМА] Похоже клиент отключился"
7. При завершении спроси о вопросах кандидата и поблагодари

ВАЖНО: Отвечай естественно и разговорно, как живой интервьюер!

ЗАВЕРШЕНИЕ ИНТЕРВЬЮ:
Когда нужно завершить интервью (время истекло, получена достаточная информация), 
используй фразу типа:
- "Спасибо за интересную беседу! Интервью подходит к концу. У тебя есть вопросы ко мне?"

ФИНАЛЬНАЯ ФРАЗА после которой конец интервью:
- До скорой встречи!

ЗАВЕРШАЙ ИНТЕРВЬЮ, если:
- Прошло >80% времени И получил основную информацию
- Кандидат дал полные ответы по всем ключевым областям
- Возникли технические проблемы или кандидат просит завершить

СТИЛЬ: Дружелюбный, профессиональный, заинтересованный в кандидате.
"""

    def get_time_info(self) -> dict[str, float]:
        """Получает информацию о времени интервью"""
        import time

        elapsed_minutes = (time.time() - self.interview_start_time) / 60
        remaining_minutes = max(0.0, self.duration_minutes - elapsed_minutes)
        time_percentage = min(100.0, (elapsed_minutes / self.duration_minutes) * 100)

        return {
            "elapsed_minutes": elapsed_minutes,
            "remaining_minutes": remaining_minutes,
            "time_percentage": time_percentage,
            "duration_minutes": self.duration_minutes,
        }

    async def track_interview_progress(self, user_response: str) -> dict[str, any]:
        """Трекает прогресс интервью для логирования"""
        current_section = self.get_current_section()
        time_info = self.get_time_info()

        return {
            "section": current_section.get("name", "Unknown"),
            "questions_asked": self.questions_asked_total,
            "section_progress": f"{self.current_section + 1}/{len(self.sections)}",
            "user_response_length": len(user_response),
            "elapsed_minutes": f"{time_info['elapsed_minutes']:.1f}",
            "remaining_minutes": f"{time_info['remaining_minutes']:.1f}",
            "time_percentage": f"{time_info['time_percentage']:.0f}%",
        }


async def entrypoint(ctx: JobContext):
    """Точка входа для AI агента"""
    logger.info("[INIT] Starting AI Interviewer Agent")
    logger.info(f"[INIT] Room: {ctx.room.name}")

    # План интервью - получаем из метаданных сессии
    interview_plan = {}
    session_id = None
    vacancy_data = None

    # Проверяем файлы команд для получения сессии
    command_file = "agent_commands.json"
    metadata_file = None

    # Ожидаем команды от менеджера
    for _ in range(60):  # Ждем до 60 секунд
        if os.path.exists(command_file):
            try:
                with open(command_file, encoding="utf-8") as f:
                    command = json.load(f)

                if (
                    command.get("action") == "start_session"
                    and command.get("room_name") == ctx.room.name
                ):
                    session_id = command.get("session_id")
                    metadata_file = command.get("metadata_file")
                    logger.info(
                        f"[INIT] Received start_session command for session {session_id}"
                    )
                    break

            except Exception as e:
                logger.warning(f"[INIT] Failed to parse command file: {str(e)}")

        await asyncio.sleep(1)

    # Загружаем метаданные сессии
    if metadata_file and os.path.exists(metadata_file):
        try:
            with open(metadata_file, encoding="utf-8") as f:
                metadata = json.load(f)
                interview_plan = metadata.get("interview_plan", {})
                vacancy_data = metadata.get("vacancy_data", None)
                session_id = metadata.get("session_id", session_id)
                logger.info(f"[INIT] Loaded interview plan for session {session_id}")
                if vacancy_data:
                    logger.info(f"[INIT] Loaded vacancy data from metadata: {vacancy_data.get('title', 'Unknown')}")
        except Exception as e:
            logger.warning(f"[INIT] Failed to load metadata: {str(e)}")
            interview_plan = {}
            vacancy_data = None

    # Используем дефолтный план если план пустой или нет секций
    if not interview_plan or not interview_plan.get("interview_structure", {}).get(
        "sections"
    ):
        logger.info("[INIT] Using default interview plan")
        interview_plan = {
            "interview_structure": {
                "duration_minutes": 5,  # ТЕСТОВЫЙ РЕЖИМ - 5 минут
                "greeting": "Привет! Это быстрое тестовое интервью на 5 минут. Готов?",
                "sections": [
                    {
                        "name": "Знакомство",
                        "duration_minutes": 1,
                        "questions": ["Расскажи кратко о себе одним предложением"],
                    },
                    {
                        "name": "Завершение",
                        "duration_minutes": 1,
                        "questions": ["Спасибо! Есть вопросы ко мне?"],
                    },
                ],
            },
            "candidate_info": {
                "name": "Тестовый кандидат",
                "skills": ["Python", "React"],
                "total_years": 3,
            },
            "focus_areas": ["quick_test"],
            "key_evaluation_points": ["Коммуникация"],
        }

    interviewer = InterviewAgent(interview_plan, vacancy_data)
    logger.info(
        f"[INIT] InterviewAgent created with {len(interviewer.sections)} sections"
    )

    # STT
    stt = (
        deepgram.STT(
            model="nova-2-general", language="ru", api_key=settings.deepgram_api_key
        )
        if settings.deepgram_api_key
        else openai.STT(
            model="whisper-1", language="ru", api_key=settings.openai_api_key
        )
    )

    # LLM
    llm = openai.LLM(
        model="gpt-4o-mini", api_key=settings.openai_api_key, temperature=0.7
    )

    # TTS
    tts = (
        cartesia.TTS(
            model="sonic-turbo",
            language="ru",
            voice="da05e96d-ca10-4220-9042-d8acef654fa9",
            api_key=settings.cartesia_api_key,
        )
        if settings.cartesia_api_key
        else silero.TTS(language="ru", model="v4_ru")
    )

    # Создаем обычный Agent и Session
    agent = Agent(instructions=interviewer.get_system_instructions())

    # Создаем AgentSession с обычным TTS и детекцией неактивности пользователя
    session = AgentSession(
        vad=silero.VAD.load(), 
        stt=stt, 
        llm=llm, 
        tts=tts,
        user_away_timeout=7.0  # 7 секунд неактивности для срабатывания away
    )

    # --- Сохранение диалога в БД ---
    async def save_dialogue_to_db(room_name: str, dialogue_history: list):
        try:
            session_generator = get_session()
            db = await anext(session_generator)
            try:
                interview_repo = InterviewRepository(db)
                resume_repo = ResumeRepository(db)
                finalization_service = InterviewFinalizationService(
                    interview_repo, resume_repo
                )
                success = await finalization_service.save_dialogue_to_session(
                    room_name, dialogue_history
                )
                if not success:
                    logger.warning(
                        f"[DB] Failed to save dialogue for room: {room_name}"
                    )
            finally:
                await session_generator.aclose()
        except Exception as e:
            logger.error(f"[DB] Error saving dialogue: {str(e)}")

    # --- Логика завершения интервью ---
    async def finalize_interview(room_name: str, interviewer_instance):
        """Завершение интервью и запуск анализа"""

        # Проверяем, не завершено ли уже интервью
        if interviewer_instance.interview_finalized:
            logger.info(f"[FINALIZE] Interview already finalized for room: {room_name}")
            return

        interviewer_instance.interview_finalized = True

        try:
            logger.info(
                f"[FINALIZE] Starting interview finalization for room: {room_name}"
            )

            # Собираем метрики интервью
            time_info = interviewer_instance.get_time_info()
            interview_metrics = {
                "total_messages": interviewer_instance.questions_asked_total,
                "dialogue_length": len(interviewer_instance.conversation_history),
                "elapsed_minutes": time_info["elapsed_minutes"],
                "planned_duration": time_info["duration_minutes"],
                "time_percentage": time_info["time_percentage"],
            }

            session_generator = get_session()
            db = await anext(session_generator)
            try:
                interview_repo = InterviewRepository(db)
                resume_repo = ResumeRepository(db)
                finalization_service = InterviewFinalizationService(
                    interview_repo, resume_repo
                )

                # Используем сервис для завершения интервью
                result = await finalization_service.finalize_interview(
                    room_name=room_name,
                    dialogue_history=interviewer_instance.conversation_history,
                    interview_metrics=interview_metrics,
                )

                if result:
                    logger.info(
                        f"[FINALIZE] Interview successfully finalized: session_id={result['session_id']}, task_id={result['analysis_task_id']}"
                    )

                else:
                    logger.error(
                        f"[FINALIZE] Failed to finalize interview for room: {room_name}"
                    )
            finally:
                await session_generator.aclose()
        except Exception as e:
            logger.error(f"[FINALIZE] Error finalizing interview: {str(e)}")

    # --- Проверка завершения интервью по ключевым фразам ---
    async def check_interview_completion_by_keywords(agent_text: str):
        """Проверяет завершение интервью по ключевым фразам"""
        # Ключевые фразы для завершения интервью
        ending_keywords = ["До скорой встречи"]

        text_lower = agent_text.lower()

        for keyword in ending_keywords:
            if keyword.lower() in text_lower:
                logger.info(
                    f"[KEYWORD_DETECTION] Found ending keyword: '{keyword}' in agent response"
                )

                if not interviewer.interview_finalized:
                    await complete_interview_sequence(
                        ctx.room.name, interviewer
                    )
                    break

        return False

    # --- Мониторинг команд завершения ---
    async def monitor_end_commands():
        """Мониторит команды завершения сессии"""
        command_file = "agent_commands.json"

        while not interviewer.interview_finalized:
            try:
                if os.path.exists(command_file):
                    with open(command_file, encoding="utf-8") as f:
                        command = json.load(f)

                    if (
                        command.get("action") == "end_session"
                        and command.get("session_id") == session_id
                    ):
                        logger.info(
                            f"[COMMAND] Received end_session command for session {session_id}"
                        )

                        if not interviewer.interview_finalized:
                            await complete_interview_sequence(
                                ctx.room.name, interviewer
                            )
                            break

                await asyncio.sleep(1)  # Проверяем каждые 1 секунды

            except Exception as e:
                logger.error(f"[COMMAND] Error monitoring commands: {str(e)}")
                await asyncio.sleep(5)

    # Запускаем мониторинг команд в фоне
    asyncio.create_task(monitor_end_commands())
    
    # --- Обработчик состояния пользователя (замена мониторинга тишины) ---
    disconnect_timer: asyncio.Task | None = None
    
    @session.on("user_state_changed")
    def on_user_state_changed(event):
        """Обработчик изменения состояния пользователя (активен/неактивен)"""
        
        async def on_change():
            nonlocal disconnect_timer

            logger.info(f"[USER_STATE] User state changed to: {event.new_state}")

            # === Пользователь начал говорить ===
            if event.new_state == "speaking":
                # Если есть таймер на 30 секунд — отменяем его
                if disconnect_timer is not None:
                    logger.info("[USER_STATE] Cancelling disconnect timer due to speaking")
                    disconnect_timer.cancel()
                    disconnect_timer = None

            # === Пользователь молчит более 10 секунд (state == away) ===
            elif event.new_state == "away" and interviewer.intro_done:
                logger.info("[USER_STATE] User away detected, sending check-in message...")

                # 1) Первое сообщение — проверка связи
                handle = await session.generate_reply(
                    instructions=(
                        "Клиент молчит уже больше 10 секунд. "
                        "Проверь связь фразой вроде 'Приём! Ты меня слышишь?' "
                        "или 'Связь не пропала?'"
                    )
                )
                await handle  # ждем завершения первой реплики

                # 2) Таймер на 30 секунд
                async def disconnect_timeout():
                    try:
                        await asyncio.sleep(30)
                        logger.info("[DISCONNECT_TIMER] 30 seconds passed, sending disconnect message")

                        # Второе сообщение — считаем, что клиент отключился
                        await session.generate_reply(
                            instructions="Похоже клиент отключился"
                        )
                        
                        logger.info("[DISCONNECT_TIMER] Disconnect message sent successfully")
                    except asyncio.CancelledError:
                        logger.info("[DISCONNECT_TIMER] Timer cancelled before completion")
                    except Exception as e:
                        logger.error(f"[DISCONNECT_TIMER] Error in disconnect timeout: {e}")

                # 3) Если уже есть активный таймер — отменяем его перед запуском нового
                if disconnect_timer is not None:
                    disconnect_timer.cancel()

                disconnect_timer = asyncio.create_task(disconnect_timeout())

        asyncio.create_task(on_change())

    # --- Полная цепочка завершения интервью ---
    async def complete_interview_sequence(room_name: str, interviewer_instance):
        """
        Полная цепочка завершения интервью:
        1. Финализация диалога в БД
        2. Закрытие комнаты LiveKit
        3. Завершение процесса агента
        """
        logger.info("[SEQUENCE] Starting interview completion sequence")

        # Шаг 1: Финализируем интервью в БД
        logger.info("[SEQUENCE] Step 1: Finalizing interview in database")
        await finalize_interview(room_name, interviewer_instance)
        logger.info("[SEQUENCE] Step 1: Database finalization completed")

        # Даём время на завершение всех DB операций
        await asyncio.sleep(1)

        # Шаг 2: Закрываем комнату LiveKit
        logger.info("[SEQUENCE] Step 2: Closing LiveKit room")
        try:
            await close_room(room_name)
            logger.info(f"[SEQUENCE] Step 2: Room {room_name} closed successfully")
        except Exception as e:
            logger.error(f"[SEQUENCE] Step 2: Failed to close room: {str(e)}")
            logger.info(
                "[SEQUENCE] Step 2: Room closure failed, but continuing sequence"
            )

    
    # --- Упрощенная логика обработки пользовательского ответа ---
    async def handle_user_input(user_response: str):
        
        current_section = interviewer.get_current_section()

        # Сохраняем ответ пользователя
        dialogue_message = {
            "role": "user",
            "content": str(user_response)
            .encode("utf-8")
            .decode("utf-8"),  # Принудительное UTF-8
            "timestamp": datetime.utcnow().isoformat(),
            "section": current_section.get("name", "Unknown"),
        }
        interviewer.conversation_history.append(dialogue_message)
        await save_dialogue_to_db(ctx.room.name, interviewer.conversation_history)

        # Обновляем прогресс интервью
        if not interviewer.intro_done:
            interviewer.intro_done = True

        # Обновляем счетчик сообщений и треким время
        interviewer.questions_asked_total += 1
        progress_info = await interviewer.track_interview_progress(user_response)
        logger.info(
            f"[PROGRESS] Messages: {progress_info['questions_asked']}, Time: {progress_info['elapsed_minutes']}min/{progress_info['time_percentage']}"
        )

        # Обновляем инструкции агента с текущим прогрессом
        try:
            updated_instructions = interviewer.get_system_instructions()
            await agent.update_instructions(updated_instructions)
        except Exception as e:
            logger.error(f"[ERROR] Failed to update instructions: {str(e)}")

    @session.on("conversation_item_added")
    def on_conversation_item(event):
        role = event.item.role
        text = event.item.text_content

        if role == "user":
            asyncio.create_task(handle_user_input(text))
        elif role == "assistant":
            
            # Сохраняем ответ агента в историю диалога
            current_section = interviewer.get_current_section()
            interviewer.conversation_history.append(
                {
                    "role": "assistant",
                    "content": str(text)
                    .encode("utf-8")
                    .decode("utf-8"),  # Принудительное UTF-8
                    "timestamp": datetime.utcnow().isoformat(),
                    "section": current_section.get("name", "Unknown"),
                }
            )

            # Сохраняем диалог в БД
            asyncio.create_task(
                save_dialogue_to_db(ctx.room.name, interviewer.conversation_history)
            )

            # Проверяем ключевые фразы для завершения интервью
            asyncio.create_task(check_interview_completion_by_keywords(text))

    await session.start(agent=agent, room=ctx.room)
    logger.info("[INIT] AI Interviewer started")


def main():
    logging.basicConfig(level=logging.INFO)
    asyncio.set_event_loop_policy(
        asyncio.WindowsSelectorEventLoopPolicy()
    )  # фикс для Windows
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))


if __name__ == "__main__":
    main()
