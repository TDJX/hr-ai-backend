import asyncio
import json
import logging
from datetime import datetime

from livekit import rtc

from rag.settings import settings

logger = logging.getLogger(__name__)


class AIInterviewerService:
    """Сервис AI интервьюера, который подключается к LiveKit комнате как участник"""

    def __init__(self, interview_session_id: int, resume_data: dict):
        self.interview_session_id = interview_session_id
        self.resume_data = resume_data
        self.room: rtc.Room | None = None
        self.audio_source: rtc.AudioSource | None = None
        self.conversation_history: list[dict] = []
        self.current_question_index = 0
        self.interview_questions = []

    async def connect_to_room(self, room_name: str, token: str):
        """Подключение AI агента к LiveKit комнате"""
        try:
            self.room = rtc.Room()

            # Настройка обработчиков событий
            self.room.on("participant_connected", self.on_participant_connected)
            self.room.on("track_subscribed", self.on_track_subscribed)
            self.room.on("data_received", self.on_data_received)

            # Подключение к комнате
            await self.room.connect(settings.livekit_url, token)
            logger.info(f"AI agent connected to room: {room_name}")

            # Создание аудио источника для TTS
            self.audio_source = rtc.AudioSource(sample_rate=16000, num_channels=1)
            track = rtc.LocalAudioTrack.create_audio_track(
                "ai_voice", self.audio_source
            )

            # Публикация аудио трека
            await self.room.local_participant.publish_track(
                track, rtc.TrackPublishOptions()
            )

            # Генерация первого вопроса
            await self.generate_interview_questions()
            await self.start_interview()

        except Exception as e:
            logger.error(f"Error connecting to room: {str(e)}")
            raise

    async def on_participant_connected(self, participant: rtc.RemoteParticipant):
        """Обработка подключения пользователя"""
        logger.info(f"Participant connected: {participant.identity}")
        # Можем отправить приветственное сообщение
        await self.send_message({"type": "ai_speaking_start"})

    async def on_track_subscribed(
        self,
        track: rtc.Track,
        publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ):
        """Обработка получения аудио трека от пользователя"""
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            logger.info("Subscribed to user audio track")
            # Настройка обработки аудио для STT
            audio_stream = rtc.AudioStream(track)
            asyncio.create_task(self.process_user_audio(audio_stream))

    async def on_data_received(self, data: bytes, participant: rtc.RemoteParticipant):
        """Обработка сообщений от фронтенда"""
        try:
            message = json.loads(data.decode())
            await self.handle_frontend_message(message)
        except Exception as e:
            logger.error(f"Error processing data message: {str(e)}")

    async def handle_frontend_message(self, message: dict):
        """Обработка сообщений от фронтенда"""
        msg_type = message.get("type")

        if msg_type == "start_interview":
            await self.start_interview()
        elif msg_type == "end_interview":
            await self.end_interview()
        elif msg_type == "user_finished_speaking":
            # Пользователь закончил говорить, можем обрабатывать его ответ
            pass

    async def process_user_audio(self, audio_stream: rtc.AudioStream):
        """Обработка аудио от пользователя через STT"""
        try:
            # Здесь будет интеграция с STT сервисом
            # Пока заглушка
            async for audio_frame in audio_stream:
                # TODO: Отправить аудио в STT (Whisper API)
                # user_text = await self.speech_to_text(audio_frame)
                # if user_text:
                #     await self.process_user_response(user_text)
                pass
        except Exception as e:
            logger.error(f"Error processing user audio: {str(e)}")

    async def generate_interview_questions(self):
        """Генерация вопросов для интервью на основе резюме"""
        try:
            from rag.registry import registry

            chat_model = registry.get_chat_model()

            # Используем существующую логику генерации вопросов
            questions_prompt = f"""
            Сгенерируй 8 вопросов для голосового собеседования кандидата.
            
            РЕЗЮМЕ КАНДИДАТА:
            Имя: {self.resume_data.get("name", "Не указано")}
            Навыки: {", ".join(self.resume_data.get("skills", []))}
            Опыт работы: {self.resume_data.get("total_years", 0)} лет
            Образование: {self.resume_data.get("education", "Не указано")}
            
            ВАЖНО:
            1. Вопросы должны быть короткими и ясными для голосового формата
            2. Начни с простого приветствия и представления
            3. Каждый вопрос должен занимать не более 2-3 предложений
            4. Используй естественную разговорную речь
            
            Верни только JSON массив строк с вопросами:
            ["Привет! Расскажи немного о себе", "Какой у тебя опыт в...", ...]
            """

            from langchain.schema import HumanMessage, SystemMessage

            messages = [
                SystemMessage(
                    content="Ты HR интервьюер. Говори естественно и дружелюбно."
                ),
                HumanMessage(content=questions_prompt),
            ]

            response = chat_model.get_llm().invoke(messages)
            response_text = response.content.strip()

            # Парсим JSON ответ
            if response_text.startswith("[") and response_text.endswith("]"):
                self.interview_questions = json.loads(response_text)
            else:
                # Fallback вопросы
                self.interview_questions = [
                    "Привет! Расскажи немного о себе и своем опыте",
                    "Что тебя привлекает в этой позиции?",
                    "Расскажи о своем самом значимом проекте",
                    "Какие технологии ты используешь в работе?",
                    "Как ты решаешь сложные задачи?",
                    "Есть ли у тебя вопросы ко мне?",
                ]

            logger.info(
                f"Generated {len(self.interview_questions)} interview questions"
            )

        except Exception as e:
            logger.error(f"Error generating questions: {str(e)}")
            # Используем базовые вопросы
            self.interview_questions = [
                "Привет! Расскажи о своем опыте",
                "Что тебя интересует в этой позиции?",
                "Есть ли у тебя вопросы?",
            ]

    async def start_interview(self):
        """Начало интервью"""
        if not self.interview_questions:
            await self.generate_interview_questions()

        # Отправляем первый вопрос
        await self.ask_next_question()

    async def ask_next_question(self):
        """Задать следующий вопрос"""
        if self.current_question_index >= len(self.interview_questions):
            await self.end_interview()
            return

        question = self.interview_questions[self.current_question_index]

        # Отправляем сообщение фронтенду
        await self.send_message(
            {
                "type": "question",
                "text": question,
                "questionNumber": self.current_question_index + 1,
            }
        )

        # Конвертируем в речь и воспроизводим
        # TODO: Реализовать TTS
        # audio_data = await self.text_to_speech(question)
        # await self.play_audio(audio_data)

        self.current_question_index += 1
        logger.info(f"Asked question {self.current_question_index}: {question}")

    async def process_user_response(self, user_text: str):
        """Обработка ответа пользователя"""
        # Сохраняем ответ в историю
        self.conversation_history.append(
            {
                "type": "user_response",
                "text": user_text,
                "timestamp": datetime.utcnow().isoformat(),
                "question_index": self.current_question_index - 1,
            }
        )

        # Можем добавить анализ ответа через LLM
        # И решить - задать уточняющий вопрос или перейти к следующему

        # Пока просто переходим к следующему вопросу
        await asyncio.sleep(1)  # Небольшая пауза
        await self.ask_next_question()

    async def send_message(self, message: dict):
        """Отправка сообщения фронтенду"""
        if self.room:
            data = json.dumps(message).encode()
            await self.room.local_participant.publish_data(data)

    async def play_audio(self, audio_data: bytes):
        """Воспроизведение аудио через LiveKit"""
        if self.audio_source:
            # TODO: Конвертировать audio_data в нужный формат и отправить
            pass

    async def end_interview(self):
        """Завершение интервью"""
        await self.send_message(
            {
                "type": "interview_complete",
                "summary": f"Interview completed with {len(self.conversation_history)} responses",
            }
        )

        # Сохраняем транскрипт в базу данных
        transcript = json.dumps(self.conversation_history, ensure_ascii=False, indent=2)

        # TODO: Обновить interview_session в БД с транскриптом

        logger.info("Interview completed")

        # Отключение от комнаты
        if self.room:
            await self.room.disconnect()


class AIInterviewerManager:
    """Менеджер для управления AI интервьюерами"""

    def __init__(self):
        self.active_sessions: dict[int, AIInterviewerService] = {}

    async def start_interview_session(
        self, interview_session_id: int, room_name: str, resume_data: dict
    ):
        """Запуск AI интервьюера для сессии"""
        try:
            # Создаем токен для AI агента
            # Нужно создать специальный токен для AI агента

            ai_interviewer = AIInterviewerService(interview_session_id, resume_data)

            # TODO: Генерировать токен для AI агента
            # ai_token = generate_ai_agent_token(room_name)
            # await ai_interviewer.connect_to_room(room_name, ai_token)

            self.active_sessions[interview_session_id] = ai_interviewer

            logger.info(f"Started AI interviewer for session: {interview_session_id}")

        except Exception as e:
            logger.error(f"Error starting AI interviewer: {str(e)}")
            raise

    async def stop_interview_session(self, interview_session_id: int):
        """Остановка AI интервьюера"""
        if interview_session_id in self.active_sessions:
            ai_interviewer = self.active_sessions[interview_session_id]
            await ai_interviewer.end_interview()
            del self.active_sessions[interview_session_id]
            logger.info(f"Stopped AI interviewer for session: {interview_session_id}")


# Глобальный менеджер
ai_interviewer_manager = AIInterviewerManager()
