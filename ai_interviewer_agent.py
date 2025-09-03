# -*- coding: utf-8 -*-
import asyncio
import json
import logging
import os
from typing import Dict, List
from datetime import datetime

# Принудительно устанавливаем UTF-8 для Windows
if os.name == 'nt':  # Windows
    import sys
    if hasattr(sys, 'stdout') and hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    WorkerOptions,
    cli,
)
from livekit.plugins import openai, deepgram, cartesia, silero, resemble
from rag.settings import settings

logger = logging.getLogger("ai-interviewer")
logger.setLevel(logging.INFO)

class InterviewAgent:
    """AI Agent для проведения собеседований с управлением диалогом"""
    
    def __init__(self, interview_plan: Dict):
        self.interview_plan = interview_plan
        self.conversation_history = []
        
        # Состояние диалога
        self.current_section = 0
        self.current_question_in_section = 0
        self.questions_asked_total = 0
        self.waiting_for_response = False
        self.last_question = None
        self.last_user_response = None
        
        # Извлекаем структуру интервью
        self.sections = self.interview_plan.get('interview_structure', {}).get('sections', [])
        self.total_sections = len(self.sections)
    
    def get_current_section(self) -> Dict:
        """Получить текущую секцию интервью"""
        if self.current_section < len(self.sections):
            return self.sections[self.current_section]
        return {}
    
    def get_next_question(self) -> str:
        """Получить следующий вопрос из текущей секции"""
        section = self.get_current_section()
        questions = section.get('questions', [])
        
        if self.current_question_in_section < len(questions):
            return questions[self.current_question_in_section]
        return None
    
    def move_to_next_question(self):
        """Переход к следующему вопросу"""
        section = self.get_current_section()
        questions = section.get('questions', [])
        
        self.current_question_in_section += 1
        self.questions_asked_total += 1
        
        # Если вопросы в секции закончились, переходим к следующей
        if self.current_question_in_section >= len(questions):
            self.move_to_next_section()
    
    def move_to_next_section(self):
        """Переход к следующей секции"""
        self.current_section += 1
        self.current_question_in_section = 0
        
        if self.current_section < len(self.sections):
            logger.info(f"Переход к секции: {self.sections[self.current_section].get('name', 'Unnamed')}")
    
    def is_interview_complete(self) -> bool:
        """Проверяет, завершено ли интервью"""
        return self.current_section >= len(self.sections)
    
    async def analyze_user_response(self, response: str, chat_model) -> Dict[str, str]:
        """Анализирует ответ пользователя и решает следующий шаг"""
        try:
            from rag.registry import registry
            
            analysis_prompt = f"""
            Проанализируй ответ кандидата на интервью и определи следующий шаг.
            
            КОНТЕКСТ:
            - Текущая секция: {self.get_current_section().get('name', 'Unknown')}
            - Заданный вопрос: {self.last_question}
            - Ответ кандидата: {response}
            
            Оцени ответ и определи действие:
            1. "continue" - ответ полный, переходим к следующему вопросу
            2. "clarify" - нужно уточнить или углубить ответ
            3. "redirect" - нужно перенаправить на тему
            
            Ответь в JSON формате:
            {{
                "action": "continue|clarify|redirect",
                "reason": "Объяснение решения",
                "follow_up_question": "Уточняющий вопрос если action=clarify или redirect"
            }}
            """
            
            from langchain.schema import HumanMessage, SystemMessage
            messages = [
                SystemMessage(content="Ты эксперт-аналитик интервью. Анализируй ответы объективно."),
                HumanMessage(content=analysis_prompt)
            ]
            
            response_analysis = chat_model.chat(messages)
            response_text = response_analysis.content.strip()
            
            # Парсим JSON ответ
            if response_text.startswith('{') and response_text.endswith('}'):
                return json.loads(response_text)
            else:
                # Fallback
                return {
                    "action": "continue",
                    "reason": "Не удалось проанализировать ответ",
                    "follow_up_question": ""
                }
                
        except Exception as e:
            logger.error(f"Ошибка анализа ответа: {str(e)}")
            return {
                "action": "continue",
                "reason": "Ошибка анализа",
                "follow_up_question": ""
            }
    
    def _extract_questions_from_plan(self) -> List[str]:
        """Извлечение вопросов из готового плана интервью"""
        questions = []
        
        try:
            # Начинаем с приветствия из плана
            greeting = self.interview_plan.get('interview_structure', {}).get('greeting', 'Привет! Готов к интервью?')
            questions.append(greeting)
            
            # Извлекаем вопросы из секций
            sections = self.interview_plan.get('interview_structure', {}).get('sections', [])
            
            for section in sections:
                section_questions = section.get('questions', [])
                questions.extend(section_questions)
            
            return questions
            
        except Exception as e:
            logger.error(f"Ошибка извлечения вопросов из плана: {str(e)}")
            # Fallback вопросы
            return [
                "Привет! Расскажи немного о себе",
                "Какой у тебя опыт работы?",
                "Что тебя привлекает в этой позиции?",
                "Есть ли у тебя вопросы ко мне?"
            ]
    
    def get_system_instructions(self) -> str:
        """Системные инструкции для AI агента"""
        candidate_info = self.interview_plan.get('candidate_info', {})
        interview_structure = self.interview_plan.get('interview_structure', {})
        focus_areas = self.interview_plan.get('focus_areas', [])
        
        greeting = interview_structure.get('greeting', 'Привет! Готов к интервью?')
        
        current_section = self.get_current_section()
        current_section_name = current_section.get('name', 'Неизвестно')
        progress = f"{self.current_section + 1}/{len(self.sections)}"
        
        return f"""Ты опытный HR-интервьюер, который проводит структурированное голосовое собеседование.

ИНФОРМАЦИЯ О КАНДИДАТЕ:
- Имя: {candidate_info.get('name', 'Кандидат')}
- Опыт работы: {candidate_info.get('total_years', 0)} лет
- Ключевые навыки: {', '.join(candidate_info.get('skills', []))}

ТЕКУЩЕЕ СОСТОЯНИЕ ИНТЕРВЬЮ:
- Прогресс: {progress} секций
- Текущая секция: {current_section_name}
- Вопросов задано: {self.questions_asked_total}

ПЛАН ИНТЕРВЬЮ:
{json.dumps(interview_structure.get('sections', []), ensure_ascii=False, indent=2)}

ТВОЯ ЗАДАЧА:
1. Веди живое интерактивное интервью
2. Анализируй каждый ответ кандидата
3. Принимай решения:
   - Если ответ полный и достаточный → переходи к следующему вопросу
   - Если ответ поверхностный → задавай уточняющие вопросы
   - Если кандидат ушел от темы → мягко возвращай к вопросу
4. Поддерживай естественный диалог

ПРАВИЛА ВЕДЕНИЯ ДИАЛОГА:
✅ Говори только на русском языке
✅ Задавай один вопрос за раз и жди ответа
✅ Анализируй качество и полноту каждого ответа
✅ Адаптируй следующие вопросы под полученные ответы
✅ Показывай искреннюю заинтересованность
✅ Если ответ неполный - углубляйся: "Расскажи подробнее...", "А как именно ты..."
✅ При переходе между секциями делай плавные переходы
✅ Завершай интервью благодарностью и следующими шагами

ПРИМЕРЫ РЕАКЦИЙ НА ОТВЕТЫ:
- Короткий ответ: "Интересно! А можешь рассказать конкретный пример?"
- Хороший ответ: "Отлично! Давай перейдем к следующему вопросу..."
- Уход от темы: "Понимаю, но давай вернемся к..."

НАЧНИ С ПРИВЕТСТВИЯ: {greeting}
"""


async def entrypoint(ctx: JobContext):
    """Точка входа для AI агента"""
    logger.info("Starting AI Interviewer Agent")
    
    # Получаем данные о резюме из метаданных комнаты
    room_metadata = ctx.room.metadata if ctx.room.metadata else "{}"
    try:
        metadata = json.loads(room_metadata)
        interview_plan = metadata.get("interview_plan", {})
        if not hasattr(interview_plan, 'interview_structure'):
            raise ValueError
    except:
        # Fallback план для тестирования
        interview_plan = {
            "interview_structure": {
                "duration_minutes": 30,
                "greeting": "Привет! Готов к тестовому интервью?",
                "sections": [
                    {
                        "name": "Знакомство",
                        "duration_minutes": 10,
                        "questions": ["Расскажи о себе", "Что тебя привлекло в этой позиции?"]
                    },
                    {
                        "name": "Технические навыки",
                        "duration_minutes": 15,
                        "questions": ["Расскажи о своем опыте с Python", "Какие проекты разрабатывал?"]
                    },
                    {
                        "name": "Вопросы кандидата",
                        "duration_minutes": 5,
                        "questions": ["Есть ли у тебя вопросы ко мне?"]
                    }
                ]
            },
            "focus_areas": ["technical_skills", "experience"],
            "candidate_info": {
                "name": "Тестовый кандидат",
                "skills": ["Python", "React", "PostgreSQL"],
                "total_years": 3,
                "education": "Высшее техническое"
            }
        }
    
    logger.info(f"Interview plan: {interview_plan}")
    
    # Создаем интервьюера с планом
    interviewer = InterviewAgent(interview_plan)
    
    # Настройка STT (Speech-to-Text)
    if hasattr(settings, 'deepgram_api_key') and settings.deepgram_api_key:
        stt = deepgram.STT(
            model="nova-2-general",
            language="ru",  # Русский язык
            api_key=settings.deepgram_api_key
        )
    else:
        # Fallback на OpenAI Whisper
        stt = openai.STT(
            model="whisper-1",
            language="ru",
            api_key=settings.openai_api_key
        )
    
    # Настройка LLM
    llm = openai.LLM(
        model="gpt-4o-mini",
        api_key=settings.openai_api_key,
        temperature=0.7,
    )
    
    # Настройка TTS (Text-to-Speech)  
    if hasattr(settings, 'resemble_api_key') and settings.resemble_api_key:
        tts = resemble.TTS(
            voice_uuid="55592656",
            api_key=settings.resemble_api_key
        )
    else:
        # Fallback на локальный TTS
        tts = silero.TTS(
            language="ru",
            model="v4_ru"
        )
    
    # Создание агента с системными инструкциями
    agent = Agent(
        instructions=interviewer.get_system_instructions()
    )
    
    # Создание сессии агента
    session = AgentSession(
        vad=silero.VAD.load(),  # Voice Activity Detection
        stt=stt,
        llm=llm,
        tts=tts,
    )
    
    # Добавляем обработчики событий с управлением диалогом
    @session.on("user_speech_committed")
    def on_user_speech(msg):
        """Синхронный callback. Внутри создаётся async-задача."""

        async def handler():
            user_response = msg.content
            logger.info(f"User said: {user_response}")

            # Сохраняем историю
            interviewer.conversation_history.append({
                "role": "user",
                "content": user_response,
                "timestamp": datetime.utcnow().isoformat(),
                "section": interviewer.get_current_section().get('name', 'Unknown')
            })

            interviewer.last_user_response = user_response
            interviewer.waiting_for_response = False

            try:
                # Анализ ответа
                analysis = await interviewer.analyze_user_response(user_response, llm)
                action = analysis.get("action", "continue")

                logger.info(f"Response analysis: {action} - {analysis.get('reason', 'No reason')}")

                if action == "continue":
                    interviewer.move_to_next_question()

                    if not interviewer.is_interview_complete():
                        next_question = interviewer.get_next_question()
                        if next_question:
                            await session.say(next_question)
                            interviewer.last_question = next_question
                            interviewer.waiting_for_response = True
                    else:
                        await session.say(
                            "Спасибо за интервью! Это все вопросы, которые я хотел задать. "
                            "В ближайшее время мы свяжемся с тобой по результатам."
                        )

                elif action in ["clarify", "redirect"]:
                    follow_up = analysis.get("follow_up_question", "Можешь рассказать подробнее?")
                    await session.say(follow_up)
                    interviewer.waiting_for_response = True

            except Exception as e:
                logger.error(f"Ошибка обработки ответа пользователя: {str(e)}")
                interviewer.move_to_next_question()

        # запускаем асинхронный обработчик
        asyncio.create_task(handler())
    
    @session.on("agent_speech_committed") 
    def on_agent_speech(msg):
        """Обработка речи агента"""
        agent_response = msg.content
        logger.info(f"Agent said: {agent_response}")
        
        # Сохраняем в историю
        interviewer.conversation_history.append({
            "role": "assistant",
            "content": agent_response, 
            "timestamp": datetime.utcnow().isoformat(),
            "section": interviewer.get_current_section().get('name', 'Unknown')
        })
        
        # Если это вопрос, обновляем состояние
        if "?" in agent_response:
            interviewer.last_question = agent_response
            interviewer.waiting_for_response = True
    
    # Запускаем сессию агента
    await session.start(agent=agent, room=ctx.room)
    
    # Приветственное сообщение
    # В новой версии приветствие будет автоматически отправлено из системных инструкций
    
    logger.info("AI Interviewer started successfully")


def main():
    """Запуск агента"""
    logging.basicConfig(level=logging.INFO)
    
    # Настройки воркера
    worker_options = WorkerOptions(
        entrypoint_fnc=entrypoint,
    )
    
    # Запуск через CLI
    cli.run_app(worker_options)


if __name__ == "__main__":
    main()