import asyncio
import logging
import multiprocessing
import queue
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional, Any, Callable
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


class AgentStatus(str, Enum):
    """Статусы AI агента"""
    IDLE = "idle"
    BUSY = "busy"
    STARTING = "starting"
    STOPPING = "stopping"
    ERROR = "error"


class MessageType(str, Enum):
    """Типы сообщений между главным приложением и агентом"""
    # Команды от main app к агенту
    START_INTERVIEW = "start_interview"
    STOP_INTERVIEW = "stop_interview" 
    SHUTDOWN = "shutdown"
    
    # Ответы от агента к main app
    TRANSCRIPT = "transcript"
    QUESTION = "question"
    STATUS = "status"
    ERROR = "error"
    INTERVIEW_STARTED = "interview_started"
    INTERVIEW_ENDED = "interview_ended"
    HEARTBEAT = "heartbeat"


@dataclass
class InterviewMessage:
    """Сообщение между главным приложением и агентом"""
    type: MessageType
    data: Dict[str, Any]
    timestamp: str
    interview_id: Optional[int] = None


class AIAgentManager:
    """Менеджер для управления AI агентом через multiprocessing"""
    
    def __init__(self):
        self.agent_process: Optional[multiprocessing.Process] = None
        self.command_queue: Optional[multiprocessing.Queue] = None
        self.response_queue: Optional[multiprocessing.Queue] = None
        self.status = AgentStatus.IDLE
        self.current_interview_id: Optional[int] = None
        self.message_handler_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Коллбэки для обработки сообщений от агента
        self.transcript_callback: Optional[Callable] = None
        self.question_callback: Optional[Callable] = None
        self.status_callback: Optional[Callable] = None
        
    def set_callbacks(self, 
                     transcript_callback: Callable = None,
                     question_callback: Callable = None, 
                     status_callback: Callable = None):
        """Установить коллбэки для обработки сообщений от агента"""
        self.transcript_callback = transcript_callback
        self.question_callback = question_callback
        self.status_callback = status_callback
        
    async def start_agent_process(self) -> bool:
        """Запуск процесса AI агента"""
        if self.agent_process and self.agent_process.is_alive():
            logger.warning("Agent process is already running")
            return True
            
        try:
            logger.info("Starting AI Agent process...")
            
            # Создаем очереди для межпроцессного общения
            self.command_queue = multiprocessing.Queue(maxsize=100)
            self.response_queue = multiprocessing.Queue(maxsize=100)
            
            # Запускаем процесс агента
            self.agent_process = multiprocessing.Process(
                target=self._run_agent_worker,
                args=(self.command_queue, self.response_queue),
                name="AIAgent"
            )
            self.agent_process.start()
            
            # Запускаем обработчик сообщений
            self._running = True
            self.message_handler_task = asyncio.create_task(self._message_handler())
            
            # Ждем подтверждения запуска (с таймаутом)
            for _ in range(10):  # 5 секунд ожидания
                await asyncio.sleep(0.5)
                if self.agent_process.is_alive() and self.status != AgentStatus.STARTING:
                    break
            
            if self.agent_process.is_alive():
                self.status = AgentStatus.IDLE
                logger.info(f"✅ AI Agent process started successfully (PID: {self.agent_process.pid})")
                return True
            else:
                logger.error("❌ AI Agent process failed to start")
                await self._cleanup()
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to start AI agent: {str(e)}")
            self.status = AgentStatus.ERROR
            await self._cleanup()
            return False
    
    async def stop_agent_process(self) -> bool:
        """Остановка процесса AI агента"""
        try:
            logger.info("Stopping AI Agent process...")
            self._running = False
            
            # Останавливаем текущее интервью если есть
            if self.current_interview_id:
                await self.stop_interview()
            
            # Отменяем обработчик сообщений
            if self.message_handler_task and not self.message_handler_task.done():
                self.message_handler_task.cancel()
                try:
                    await self.message_handler_task
                except asyncio.CancelledError:
                    pass
                
            # Отправляем команду graceful shutdown
            if self.agent_process and self.agent_process.is_alive():
                self._send_command(MessageType.SHUTDOWN, {})
                
                # Ждем завершения
                for _ in range(6):  # 3 секунды
                    await asyncio.sleep(0.5)
                    if not self.agent_process.is_alive():
                        break
                
                # Принудительное завершение если нужно
                if self.agent_process.is_alive():
                    logger.warning("Force terminating agent process")
                    self.agent_process.terminate()
                    await asyncio.sleep(1)
                    
                    if self.agent_process.is_alive():
                        logger.warning("Force killing agent process")
                        self.agent_process.kill()
                        
                # Ждем завершения процесса
                if self.agent_process.is_alive():
                    try:
                        self.agent_process.join(timeout=3)
                    except Exception as e:
                        logger.error(f"Error joining process: {e}")
                
            await self._cleanup()
            logger.info("✅ AI Agent process stopped successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to stop AI agent: {str(e)}")
            await self._cleanup()
            return False
    
    async def start_interview(self, interview_id: int, interview_plan: Dict[str, Any], room_name: str) -> bool:
        """Начать интервью"""
        if self.status == AgentStatus.BUSY:
            logger.warning(f"Agent is busy with interview {self.current_interview_id}")
            return False
            
        if not self.agent_process or not self.agent_process.is_alive():
            logger.error("Agent process is not running")
            return False
            
        try:
            logger.info(f"Starting interview {interview_id} in room {room_name}")
            self.status = AgentStatus.STARTING
            self.current_interview_id = interview_id
            
            from app.core.config import settings
            
            command_data = {
                "interview_id": interview_id,
                "interview_plan": interview_plan,
                "room_name": room_name,
                "livekit_url": settings.livekit_url,
                "livekit_api_key": settings.livekit_api_key,
                "livekit_api_secret": settings.livekit_api_secret
            }
            
            self._send_command(MessageType.START_INTERVIEW, command_data)
            
            # Ждем подтверждения начала интервью
            for _ in range(20):  # 10 секунд ожидания
                await asyncio.sleep(0.5)
                if self.status == AgentStatus.BUSY:
                    logger.info(f"✅ Interview {interview_id} started successfully")
                    return True
                elif self.status == AgentStatus.ERROR:
                    break
            
            # Таймаут или ошибка
            logger.error(f"❌ Failed to start interview {interview_id} (timeout or error)")
            self.current_interview_id = None
            self.status = AgentStatus.IDLE
            return False
                
        except Exception as e:
            logger.error(f"❌ Failed to start interview: {str(e)}")
            self.status = AgentStatus.ERROR
            self.current_interview_id = None
            return False
    
    async def stop_interview(self) -> bool:
        """Остановить текущее интервью"""
        if self.status != AgentStatus.BUSY or not self.current_interview_id:
            logger.warning("No active interview to stop")
            return True
            
        try:
            interview_id = self.current_interview_id
            logger.info(f"Stopping interview {interview_id}")
            
            self.status = AgentStatus.STOPPING
            
            self._send_command(MessageType.STOP_INTERVIEW, {
                "interview_id": interview_id
            })
            
            # Ждем завершения
            for _ in range(10):  # 5 секунд
                await asyncio.sleep(0.5)
                if self.status == AgentStatus.IDLE:
                    break
            
            # Принудительная очистка если нужно
            if self.status != AgentStatus.IDLE:
                self.status = AgentStatus.IDLE
                self.current_interview_id = None
                
            logger.info(f"✅ Interview {interview_id} stopped successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to stop interview: {str(e)}")
            # Принудительная очистка
            self.status = AgentStatus.IDLE
            self.current_interview_id = None
            return False
    
    def _send_command(self, message_type: MessageType, data: Dict[str, Any]):
        """Отправить команду агенту"""
        if not self.command_queue:
            logger.error("Command queue is not available")
            return
            
        try:
            message = InterviewMessage(
                type=message_type,
                data=data,
                timestamp=datetime.now(timezone.utc).isoformat(),
                interview_id=self.current_interview_id
            )
            
            # Конвертируем в dict для JSON сериализации
            message_dict = asdict(message)
            # Конвертируем enum в строку
            message_dict["type"] = message_type.value
            
            self.command_queue.put(message_dict, timeout=2)
            logger.debug(f"📤 Sent command: {message_type.value}")
            
        except queue.Full:
            logger.error(f"❌ Command queue is full, failed to send: {message_type.value}")
        except Exception as e:
            logger.error(f"❌ Failed to send command {message_type.value}: {str(e)}")
    
    async def _message_handler(self):
        """Обработчик сообщений от агента в async цикле"""
        logger.info("📨 Message handler started")
        
        while self._running:
            try:
                if not self.response_queue:
                    await asyncio.sleep(0.1)
                    continue
                
                # Неблокирующая проверка очереди
                try:
                    message_dict = self.response_queue.get_nowait()
                    await self._handle_agent_message(message_dict)
                except queue.Empty:
                    await asyncio.sleep(0.1)
                    continue
                    
            except asyncio.CancelledError:
                logger.info("📨 Message handler cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Error in message handler: {str(e)}")
                await asyncio.sleep(1)
                
        logger.info("📨 Message handler stopped")
    
    async def _handle_agent_message(self, message_dict: Dict[str, Any]):
        """Обработка сообщения от агента"""
        try:
            message_type_str = message_dict.get("type")
            data = message_dict.get("data", {})
            interview_id = message_dict.get("interview_id")
            
            # Конвертируем строку в enum
            try:
                message_type = MessageType(message_type_str)
            except ValueError:
                logger.error(f"Unknown message type: {message_type_str}")
                return
            
            logger.debug(f"📥 Received message: {message_type.value}")

            match message_type:
                case MessageType.STATUS:
                    new_status = data.get("status")
                    if new_status and new_status in [s.value for s in AgentStatus]:
                        old_status = self.status
                        self.status = AgentStatus(new_status)
                        logger.info(f"🔄 Status changed: {old_status.value} → {self.status.value}")

                        # Коллбэк для статуса
                        if self.status_callback:
                            try:
                                await self.status_callback(self.status, data)
                            except Exception as e:
                                logger.error(f"Status callback error: {e}")
                case MessageType.TRANSCRIPT:
                    transcript_text = data.get('text', '')
                    speaker = data.get('speaker', 'unknown')
                    logger.info(f"🎙️  Transcript [{speaker}]: {transcript_text[:100]}{'...' if len(transcript_text) > 100 else ''}")

                    if self.transcript_callback:
                        try:
                            await self.transcript_callback(data)
                        except Exception as e:
                            logger.error(f"Transcript callback error: {e}")
                        
                case MessageType.QUESTION:
                    question_text = data.get('text', '')
                    logger.info(f"❓ AI Question: {question_text[:100]}{'...' if len(question_text) > 100 else ''}")

                    if self.question_callback:
                        try:
                            await self.question_callback(data)
                        except Exception as e:
                            logger.error(f"Question callback error: {e}")
                        
                case MessageType.INTERVIEW_STARTED:
                    self.status = AgentStatus.BUSY
                    logger.info(f"✅ Interview {interview_id} confirmed started")
                
                case MessageType.INTERVIEW_ENDED:
                    self.status = AgentStatus.IDLE
                    self.current_interview_id = None
                    logger.info(f"🏁 Interview {interview_id} ended")
                
                case MessageType.ERROR:
                    error_msg = data.get("error", "Unknown error")
                    logger.error(f"❌ Agent error: {error_msg}")
                    self.status = AgentStatus.ERROR

                case MessageType.HEARTBEAT:
                    # Агент жив
                    logger.debug("💓 Agent heartbeat")
                
        except Exception as e:
            logger.error(f"❌ Failed to handle agent message: {str(e)}")
    
    async def _cleanup(self):
        """Очистка ресурсов"""
        self.agent_process = None
        self.command_queue = None
        self.response_queue = None
        self.status = AgentStatus.IDLE
        self.current_interview_id = None
    
    def get_status(self) -> Dict[str, Any]:
        """Получить статус агента"""
        return {
            "status": self.status.value,
            "current_interview_id": self.current_interview_id,
            "process_alive": self.agent_process.is_alive() if self.agent_process else False,
            "process_pid": self.agent_process.pid if self.agent_process and self.agent_process.is_alive() else None,
            "queue_sizes": {
                "commands": self.command_queue.qsize() if self.command_queue else 0,
                "responses": self.response_queue.qsize() if self.response_queue else 0
            }
        }
    
    @staticmethod
    def _run_agent_worker(command_queue: multiprocessing.Queue, response_queue: multiprocessing.Queue):
        """Worker функция для запуска агента в отдельном процессе"""
        import sys
        import signal
        
        # Настраиваем логирование для worker процесса
        logging.basicConfig(
            level=logging.INFO,
            format='[AGENT-WORKER] %(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler(sys.stdout)]
        )
        worker_logger = logging.getLogger("agent-worker")
        
        # Обработчик сигналов для graceful shutdown
        shutdown_event = multiprocessing.Event()
        
        def signal_handler(signum, frame):
            worker_logger.info(f"Received signal {signum}, shutting down...")
            shutdown_event.set()
            
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        try:
            worker_logger.info("🚀 Agent worker process started")
            
            # Отправляем статус запуска
            response_queue.put({
                "type": MessageType.STATUS.value,
                "data": {"status": AgentStatus.IDLE.value},
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
            # Импортируем модули агента
            try:
                import asyncio
                from ai_interviewer_agent import entrypoint
                from livekit.agents import WorkerOptions, cli
                from livekit import api, rtc
            except ImportError as e:
                worker_logger.error(f"Failed to import agent modules: {e}")
                response_queue.put({
                    "type": MessageType.ERROR.value, 
                    "data": {"error": f"Import error: {str(e)}"},
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                return
            
            # Основной цикл обработки команд
            async def command_processing_loop():
                """Основной цикл обработки команд от главного приложения"""
                current_interview_session = None
                heartbeat_counter = 0
                
                while not shutdown_event.is_set():
                    try:
                        # Heartbeat каждые 10 итераций (~1 секунда)
                        heartbeat_counter += 1
                        if heartbeat_counter >= 10:
                            response_queue.put({
                                "type": MessageType.HEARTBEAT.value,
                                "data": {},
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            })
                            heartbeat_counter = 0
                        
                        # Проверяем команды
                        try:
                            message = command_queue.get_nowait()
                            message_type_str = message.get("type")
                            data = message.get("data", {})

                            # Конвертируем в enum
                            try:
                                message_type = MessageType(message_type_str)
                            except ValueError:
                                worker_logger.error(f"Unknown command type: {message_type_str}")
                                continue
                            
                            worker_logger.info(f"📥 Processing command: {message_type.value}")
                            
                            if message_type == MessageType.START_INTERVIEW:
                                if current_interview_session:
                                    worker_logger.warning("Interview already running, stopping previous")
                                    # TODO: Stop current interview
                                    
                                # Запускаем новое интервью
                                interview_id = data.get("interview_id")
                                interview_plan = data.get("interview_plan", {})
                                room_name = data.get("room_name")
                                
                                worker_logger.info(f"🎬 Starting interview {interview_id} in room {room_name}")
                                
                                # Обновляем статус
                                response_queue.put({
                                    "type": MessageType.STATUS.value,
                                    "data": {"status": AgentStatus.BUSY.value},
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                    "interview_id": interview_id
                                })
                                
                                response_queue.put({
                                    "type": MessageType.INTERVIEW_STARTED.value,
                                    "data": {"interview_id": interview_id},
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                    "interview_id": interview_id
                                })
                                
                                # TODO: Здесь будет реальный запуск LiveKit сессии
                                current_interview_session = {
                                    "id": interview_id,
                                    "room": room_name,
                                    "plan": interview_plan
                                }
                                
                                # Симуляция работы интервью (удалить потом)
                                await asyncio.sleep(2)
                                response_queue.put({
                                    "type": MessageType.QUESTION.value,
                                    "data": {
                                        "text": "Привет! Расскажи немного о себе",
                                        "section": "introduction"
                                    },
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                    "interview_id": interview_id
                                })
                                
                            elif message_type == MessageType.STOP_INTERVIEW:
                                if current_interview_session:
                                    interview_id = current_interview_session["id"]
                                    worker_logger.info(f"🛑 Stopping interview {interview_id}")
                                    
                                    # TODO: Остановить LiveKit сессию
                                    current_interview_session = None
                                    
                                    response_queue.put({
                                        "type": MessageType.INTERVIEW_ENDED.value,
                                        "data": {"interview_id": interview_id},
                                        "timestamp": datetime.now(timezone.utc).isoformat(),
                                        "interview_id": interview_id
                                    })
                                    
                                response_queue.put({
                                    "type": MessageType.STATUS.value,
                                    "data": {"status": AgentStatus.IDLE.value},
                                    "timestamp": datetime.now(timezone.utc).isoformat()
                                })
                                
                            elif message_type == MessageType.SHUTDOWN:
                                worker_logger.info("🔄 Graceful shutdown requested")
                                break
                                
                        except queue.Empty:
                            await asyncio.sleep(0.1)
                            continue
                            
                    except Exception as e:
                        worker_logger.error(f"❌ Error processing command: {str(e)}")
                        response_queue.put({
                            "type": MessageType.ERROR.value,
                            "data": {"error": str(e)},
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                        await asyncio.sleep(1)
            
            # Запускаем цикл команд
            asyncio.run(command_processing_loop())
            
        except Exception as e:
            worker_logger.error(f"❌ Agent worker process error: {str(e)}")
            try:
                response_queue.put({
                    "type": MessageType.ERROR.value,
                    "data": {"error": str(e)},
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            except:
                pass
        finally:
            worker_logger.info("🏁 Agent worker process ended")


# Глобальный экземпляр менеджера
agent_manager = AIAgentManager()