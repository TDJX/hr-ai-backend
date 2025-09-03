import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.session_middleware import SessionMiddleware
from app.routers import vacancy_router, resume_router
from app.routers.session_router import router as session_router
from app.routers.interview_router import router as interview_router
from app.routers.admin_router import router as admin_router
from app.services.agent_manager import agent_manager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    logger.info("🚀 Starting HR AI Backend...")
    
    # Запускаем AI Agent при старте приложения
    try:
        agent_success = await agent_manager.start_agent_process()
        if agent_success:
            logger.info("✅ AI Agent started successfully")
            
            # Устанавливаем коллбэки для обработки сообщений от агента
            agent_manager.set_callbacks(
                transcript_callback=handle_transcript,
                question_callback=handle_question,
                status_callback=handle_agent_status
            )
        else:
            logger.error("❌ Failed to start AI Agent")
    except Exception as e:
        logger.error(f"❌ Error starting AI Agent: {str(e)}")
    
    yield
    
    # Останавливаем AI Agent при завершении приложения
    logger.info("🛑 Shutting down HR AI Backend...")
    try:
        await agent_manager.stop_agent_process()
        logger.info("✅ AI Agent stopped successfully")
    except Exception as e:
        logger.error(f"❌ Error stopping AI Agent: {str(e)}")


async def handle_transcript(data: dict):
    """Обработка расшифровки речи от агента"""
    transcript = data.get("text", "")
    speaker = data.get("speaker", "unknown")
    interview_id = data.get("interview_id")
    
    logger.info(f"📝 Transcript from interview {interview_id} [{speaker}]: {transcript}")
    
    # TODO: Сохранить в базу данных
    # TODO: Отправить через WebSocket если нужно
    

async def handle_question(data: dict):
    """Обработка вопроса от AI агента"""
    question = data.get("text", "")
    section = data.get("section", "unknown")
    interview_id = data.get("interview_id")
    
    logger.info(f"❓ AI Question from interview {interview_id} [{section}]: {question}")
    
    # TODO: Сохранить вопрос в базу данных
    # TODO: Обновить статус интервью


async def handle_agent_status(status, data: dict):
    """Обработка изменения статуса агента"""
    logger.info(f"🔄 Agent status changed to: {status.value}")
    
    # TODO: Обновить статус в базе данных если нужно
    # TODO: Уведомить админов о критических изменениях


app = FastAPI(
    title="HR AI Backend",
    description="Backend API for HR AI system with vacancies and resumes management",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Добавляем middleware для управления сессиями (после CORS)
app.add_middleware(SessionMiddleware, cookie_name="session_id")

app.include_router(vacancy_router, prefix="/api/v1")
app.include_router(resume_router, prefix="/api/v1")
app.include_router(session_router, prefix="/api/v1")
app.include_router(interview_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"message": "HR AI Backend API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
