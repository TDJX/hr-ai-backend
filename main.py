from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.session_middleware import SessionMiddleware
from app.routers import resume_router, vacancy_router
from app.routers.admin_router import router as admin_router
from app.routers.analysis_router import router as analysis_router
from app.routers.interview_router import router as interview_router
from app.routers.session_router import router as session_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Запускаем AI агента при старте приложения
    from app.services.agent_manager import agent_manager

    print("[STARTUP] Starting AI Agent...")
    success = await agent_manager.start_agent()

    if success:
        print("[STARTUP] AI Agent started successfully")
    else:
        print("[STARTUP] Failed to start AI Agent")

    yield

    # Останавливаем AI агента при завершении приложения
    print("[SHUTDOWN] Stopping AI Agent...")
    await agent_manager.stop_agent()
    print("[SHUTDOWN] AI Agent stopped")


app = FastAPI(
    title="HR AI Backend",
    description="Backend API for HR AI system with vacancies and resumes management",
    version="1.0.0",
    lifespan=lifespan,
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
app.include_router(analysis_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"message": "HR AI Backend API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
