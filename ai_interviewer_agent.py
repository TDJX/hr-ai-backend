import asyncio
import json
import logging
import os
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

    def __init__(self, interview_plan: dict):
        self.interview_plan = interview_plan
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

        return f"""Ты опытный HR-интервьюер, который проводит адаптивное голосовое собеседование.

ИНФОРМАЦИЯ О КАНДИДАТЕ:
- Имя: {candidate_name}
- Опыт работы: {candidate_years} лет
- Ключевые навыки: {candidate_skills}

ПЛАН ИНТЕРВЬЮ (используй как руководство, но адаптируйся):
{sections_info}

ВРЕМЯ ИНТЕРВЬЮ:
- Запланированная длительность: {self.duration_minutes} минут
- Прошло времени: {elapsed_minutes:.1f} минут ({time_percentage:.0f}%)
- Осталось времени: {remaining_minutes:.1f} минут
- Статус времени: {time_status}

ФОКУС-ОБЛАСТИ: {focus_areas_str}
КЛЮЧЕВЫЕ ОЦЕНОЧНЫЕ ТОЧКИ: {evaluation_points_str}

ИНСТРУКЦИИ:
1. Начни с приветствия: {greeting}
2. Адаптируй вопросы под ответы кандидата
3. Следи за временем - при превышении 80% времени начинай завершать интервью
4. Оценивай качество и глубину ответов кандидата
5. Завершай интервью если:
   - Получил достаточно информации для оценки
   - Время почти истекло (>90% от запланированного)
   - Кандидат дал исчерпывающие ответы
6. При завершении спроси о вопросах кандидата и поблагодари

ВАЖНО: Отвечай естественно и разговорно, как живой интервьюер!

ЗАВЕРШЕНИЕ ИНТЕРВЬЮ:
Когда нужно завершить интервью (время истекло, получена достаточная информация), 
используй одну из этих ключевых фраз:
- "Спасибо за интересную беседу! У тебя есть вопросы ко мне?"
- "Это всё, что я хотел узнать. Есть ли у вас вопросы?"  
- "Интервью подходит к концу. У тебя есть вопросы ко мне?"
ФИНАЛЬНАЯ ФРАЗА после которой ничего не будет:
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
                session_id = metadata.get("session_id", session_id)
                logger.info(f"[INIT] Loaded interview plan for session {session_id}")
        except Exception as e:
            logger.warning(f"[INIT] Failed to load metadata: {str(e)}")
            interview_plan = {}

    # Используем дефолтный план если план пустой или нет секций
    if not interview_plan or not interview_plan.get("interview_structure", {}).get(
        "sections"
    ):
        logger.info("[INIT] Using default interview plan")
        interview_plan = {
            "interview_structure": {
                "duration_minutes": 2,  # ТЕСТОВЫЙ РЕЖИМ - 2 минуты
                "greeting": "Привет! Это быстрое тестовое интервью на 2 минуты. Готов?",
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

    interviewer = InterviewAgent(interview_plan)
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

    # Создаем AgentSession с обычным TTS
    session = AgentSession(vad=silero.VAD.load(), stt=stt, llm=llm, tts=tts)

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
                    # Запускаем полную цепочку завершения интервью
                    await complete_interview_sequence(ctx.room.name, interviewer)
                    return True
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

                await asyncio.sleep(2)  # Проверяем каждые 2 секунды

            except Exception as e:
                logger.error(f"[COMMAND] Error monitoring commands: {str(e)}")
                await asyncio.sleep(5)

    # Запускаем мониторинг команд в фоне
    asyncio.create_task(monitor_end_commands())

    # --- Полная цепочка завершения интервью ---
    async def complete_interview_sequence(room_name: str, interviewer_instance):
        """
        Полная цепочка завершения интервью:
        1. Финализация диалога в БД
        2. Закрытие комнаты LiveKit
        3. Завершение процесса агента
        """
        try:
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

            # Шаг 3: Завершаем процесс агента
            logger.info("[SEQUENCE] Step 3: Terminating agent process")
            await asyncio.sleep(2)  # Даём время на завершение всех операций
            logger.info("[SEQUENCE] Step 3: Force terminating agent process")
            import os

            os._exit(0)  # Принудительное завершение процесса

        except Exception as e:
            logger.error(f"[SEQUENCE] Error in interview completion sequence: {str(e)}")
            # Fallback: принудительно завершаем процесс даже при ошибках
            logger.info("[SEQUENCE] Fallback: Force terminating process")
            await asyncio.sleep(1)
            import os

            os._exit(1)

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
