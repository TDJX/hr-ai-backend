import logging

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.database import get_session
from app.models.session import Session
from app.repositories.session_repository import SessionRepository

logger = logging.getLogger(__name__)


class SessionMiddleware(BaseHTTPMiddleware):
    """Middleware для автоматического управления сессиями"""

    def __init__(self, app: ASGIApp, cookie_name: str = "session_id"):
        super().__init__(app)
        self.cookie_name = cookie_name

    async def dispatch(self, request: Request, call_next):
        # Пропускаем статические файлы, служебные эндпоинты и OPTIONS запросы
        if (
            request.url.path.startswith(
                ("/docs", "/redoc", "/openapi.json", "/health", "/favicon.ico")
            )
            or request.method == "OPTIONS"
        ):
            return await call_next(request)

        # Получаем session_id из cookie или заголовка
        session_id = request.cookies.get(self.cookie_name) or request.headers.get(
            "X-Session-ID"
        )

        session_obj = None

        try:
            # Работаем с БД в рамках одной async сессии
            async for db_session in get_session():
                session_repo = SessionRepository(db_session)

                # Проверяем существующую сессию
                if session_id:
                    session_obj = await session_repo.get_by_session_id(session_id)
                    if session_obj and not session_obj.is_expired():
                        # Обновляем время последней активности
                        await session_repo.update_last_activity(session_id)
                    else:
                        session_obj = None

                # Создаем новую сессию, если нет действующей
                if not session_obj:
                    user_agent = request.headers.get("User-Agent")
                    client_ip = (
                        getattr(request.client, "host", None)
                        if request.client
                        else None
                    )
                    session_obj = await session_repo.create_session(
                        user_agent=user_agent, ip_address=client_ip
                    )
                    logger.info(f"Created new session: {session_obj.session_id}")

                # Добавляем сессию в контекст запроса
                request.state.session = session_obj
                break

        except Exception as e:
            logger.error(f"Session middleware error: {e}")
            return JSONResponse(
                status_code=500, content={"error": "Session management error"}
            )

        # Выполняем запрос
        response = await call_next(request)

        # Устанавливаем cookie с session_id в ответе
        if session_obj and isinstance(response, Response):
            response.set_cookie(
                key=self.cookie_name,
                value=session_obj.session_id,
                max_age=30 * 24 * 60 * 60,  # 30 дней
                httponly=True,
                secure=False,  # Для dev среды
                samesite="lax",
            )

        return response


async def get_current_session(request: Request) -> Session:
    """Получить текущую сессию из контекста запроса"""
    return getattr(request.state, "session", None)
