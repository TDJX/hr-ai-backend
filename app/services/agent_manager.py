import asyncio
import json
import logging
import os
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime

import psutil

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class AgentProcess:
    pid: int
    session_id: int | None
    room_name: str | None
    started_at: datetime
    status: str  # "idle", "active", "stopping"


class AgentManager:
    """Singleton менеджер для управления AI агентом интервьюера"""

    _instance: "AgentManager | None" = None
    _agent_process: AgentProcess | None = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self.livekit_url = settings.livekit_url or "ws://localhost:7880"
            self.api_key = settings.livekit_api_key or "devkey"
            self.api_secret = (
                settings.livekit_api_secret or "devkey_secret_32chars_minimum_length"
            )

    async def start_agent(self) -> bool:
        """Запускает AI агента в режиме ожидания (без конкретной сессии)"""
        async with self._lock:
            if self._agent_process and self._is_process_alive(self._agent_process.pid):
                logger.info(f"Agent already running with PID {self._agent_process.pid}")
                return True

            try:
                # Запускаем агента в режиме worker (будет ждать подключения к комнатам)
                agent_cmd = [
                    "uv",
                    "run",
                    "ai_interviewer_agent.py",
                    "start",
                    "--url",
                    self.livekit_url,
                    "--api-key",
                    self.api_key,
                    "--api-secret",
                    self.api_secret,
                ]

                # Настройка окружения
                env = os.environ.copy()
                env.update(
                    {
                        "OPENAI_API_KEY": settings.openai_api_key or "",
                        "DEEPGRAM_API_KEY": settings.deepgram_api_key or "",
                        "CARTESIA_API_KEY": settings.cartesia_api_key or "",
                        "PYTHONIOENCODING": "utf-8",
                    }
                )

                # Запуск процесса
                with open("ai_agent.log", "w") as log_file:
                    process = subprocess.Popen(
                        agent_cmd,
                        env=env,
                        stdout=log_file,
                        stderr=subprocess.STDOUT,
                        cwd=".",
                    )

                self._agent_process = AgentProcess(
                    pid=process.pid,
                    session_id=None,
                    room_name=None,
                    started_at=datetime.now(UTC),
                    status="idle",
                )

                logger.info(f"AI Agent started with PID {process.pid}")
                return True

            except Exception as e:
                logger.error(f"Failed to start AI agent: {e}")
                return False

    async def stop_agent(self) -> bool:
        """Останавливает AI агента"""
        async with self._lock:
            if not self._agent_process:
                return True

            try:
                if self._is_process_alive(self._agent_process.pid):
                    process = psutil.Process(self._agent_process.pid)

                    # Сначала пытаемся graceful shutdown
                    process.terminate()

                    # Ждем до 10 секунд
                    for _ in range(100):
                        if not process.is_running():
                            break
                        await asyncio.sleep(0.1)

                    # Если не завершился, убиваем принудительно
                    if process.is_running():
                        process.kill()

                logger.info(f"AI Agent with PID {self._agent_process.pid} stopped")
                self._agent_process = None
                return True

            except Exception as e:
                logger.error(f"Error stopping AI agent: {e}")
                self._agent_process = None
                return False

    async def assign_session(
        self, session_id: int, room_name: str, interview_plan: dict, vacancy_data: dict = None
    ) -> bool:
        """Назначает агенту конкретную сессию интервью"""
        async with self._lock:
            if not self._agent_process or not self._is_process_alive(
                self._agent_process.pid
            ):
                logger.error("No active agent to assign session to")
                return False

            if self._agent_process.status == "active":
                logger.error(
                    f"Agent is busy with session {self._agent_process.session_id}"
                )
                return False

            try:
                # Создаем файл метаданных для сессии
                metadata_file = f"session_metadata_{session_id}.json"
                metadata = {
                    "session_id": session_id,
                    "room_name": room_name,
                    "interview_plan": interview_plan,
                    "command": "start_interview",
                }
                
                # Добавляем данные вакансии если они переданы
                if vacancy_data:
                    metadata["vacancy_data"] = vacancy_data
                    
                with open(metadata_file, "w", encoding="utf-8") as f:
                    json.dump(metadata, f, ensure_ascii=False, indent=2)

                # Отправляем сигнал агенту через файл команд
                command_file = "agent_commands.json"
                with open(command_file, "w", encoding="utf-8") as f:
                    json.dump(
                        {
                            "action": "start_session",
                            "session_id": session_id,
                            "room_name": room_name,
                            "metadata_file": metadata_file,
                            "timestamp": datetime.now(UTC).isoformat(),
                        },
                        f,
                        ensure_ascii=False,
                        indent=2,
                    )

                # Обновляем статус агента
                self._agent_process.session_id = session_id
                self._agent_process.room_name = room_name
                self._agent_process.status = "active"

                logger.info(
                    f"Assigned session {session_id} to agent PID {self._agent_process.pid}"
                )
                return True

            except Exception as e:
                logger.error(f"Error assigning session to agent: {e}")
                return False

    async def release_session(self) -> bool:
        """Освобождает агента от текущей сессии"""
        async with self._lock:
            if not self._agent_process:
                return True

            try:
                # Отправляем команду завершения сессии
                command_file = "agent_commands.json"
                with open(command_file, "w", encoding="utf-8") as f:
                    json.dump(
                        {
                            "action": "end_session",
                            "session_id": self._agent_process.session_id,
                            "timestamp": datetime.now(UTC).isoformat(),
                        },
                        f,
                        ensure_ascii=False,
                        indent=2,
                    )

                # Очищаем файлы метаданных
                if self._agent_process.session_id:
                    try:
                        os.remove(
                            f"session_metadata_{self._agent_process.session_id}.json"
                        )
                    except FileNotFoundError:
                        pass

                # Возвращаем агента в режим ожидания
                self._agent_process.session_id = None
                self._agent_process.room_name = None
                self._agent_process.status = "idle"

                logger.info("Released agent from current session")
                return True

            except Exception as e:
                logger.error(f"Error releasing agent session: {e}")
                return False

    def get_status(self) -> dict:
        """Возвращает текущий статус агента"""
        if not self._agent_process:
            return {
                "status": "stopped",
                "pid": None,
                "session_id": None,
                "room_name": None,
                "uptime": None,
            }

        is_alive = self._is_process_alive(self._agent_process.pid)
        if not is_alive:
            self._agent_process = None
            return {
                "status": "dead",
                "pid": None,
                "session_id": None,
                "room_name": None,
                "uptime": None,
            }

        uptime = datetime.now(UTC) - self._agent_process.started_at

        return {
            "status": self._agent_process.status,
            "pid": self._agent_process.pid,
            "session_id": self._agent_process.session_id,
            "room_name": self._agent_process.room_name,
            "uptime": str(uptime),
            "started_at": self._agent_process.started_at.isoformat(),
        }

    def is_available(self) -> bool:
        """Проверяет, доступен ли агент для новой сессии"""
        if not self._agent_process:
            return False

        if not self._is_process_alive(self._agent_process.pid):
            self._agent_process = None
            return False

        return self._agent_process.status == "idle"

    def _is_process_alive(self, pid: int) -> bool:
        """Проверяет, жив ли процесс"""
        try:
            process = psutil.Process(pid)
            return process.is_running()
        except psutil.NoSuchProcess:
            return False
        except Exception:
            return False


# Глобальный экземпляр менеджера
agent_manager = AgentManager()
