#!/usr/bin/env python3
"""
Тестирование HR-AI системы по компонентам
"""

import asyncio
import sys
import os
import requests
from pathlib import Path

# Добавляем корневую директорию в PYTHONPATH
sys.path.append(str(Path(__file__).parent))

async def test_database_connection():
    """Тест подключения к PostgreSQL"""
    print("Testing database connection...")
    
    try:
        from app.core.database import get_db
        from app.models.resume import Resume
        from sqlalchemy import select
        
        # Получаем async сессию
        async for db in get_db():
            # Пробуем выполнить простой запрос
            result = await db.execute(select(Resume).limit(1))
            resumes = result.scalars().all()
            
            print("OK Database: connection successful")
            print(f"Found resumes in database: {len(resumes)}")
            return True
            
    except Exception as e:
        print(f"FAIL Database: connection error - {str(e)}")
        return False


async def test_rag_system():
    """Тест RAG системы (парсинг резюме)"""
    print("\n🔍 Тестируем RAG систему...")
    
    try:
        from rag.registry import registry
        from rag.llm.model import ResumeParser
        
        # Инициализируем модели
        chat_model = registry.get_chat_model()
        embeddings_model = registry.get_embeddings_model()
        
        print("✅ RAG система: модели инициализированы")
        
        # Тестируем парсер резюме
        parser = ResumeParser(chat_model)
        
        # Создаем тестовый текст резюме
        test_resume_text = """
        Иван Петров
        Python разработчик
        Опыт работы: 3 года
        Навыки: Python, Django, PostgreSQL, Docker
        Образование: МГУ, факультет ВМК
        """
        
        parsed_resume = parser.parse_resume_text(test_resume_text)
        
        print("✅ RAG система: парсинг резюме работает")
        print(f"📋 Распарсенные данные: {parsed_resume}")
        
        return True
        
    except Exception as e:
        print(f"❌ RAG система: ошибка - {str(e)}")
        return False


def test_redis_connection():
    """Тест подключения к Redis"""
    print("\n🔍 Тестируем подключение к Redis...")
    
    try:
        import redis
        from rag.settings import settings
        
        r = redis.Redis(
            host=settings.redis_cache_url,
            port=settings.redis_cache_port,
            db=settings.redis_cache_db
        )
        
        # Пробуем ping
        r.ping()
        
        print("✅ Redis: подключение успешно")
        return True
        
    except Exception as e:
        print(f"❌ Redis: ошибка подключения - {str(e)}")
        print("💡 Для запуска Redis используйте: docker run -d -p 6379:6379 redis:alpine")
        return False


async def test_celery_tasks():
    """Тест Celery задач"""
    print("\n🔍 Тестируем Celery задачи...")
    
    try:
        from celery_worker.tasks import parse_resume_task
        
        print("✅ Celery: задачи импортируются")
        print("💡 Для полного теста запустите: celery -A celery_worker.celery_app worker --loglevel=info")
        
        return True
        
    except Exception as e:
        print(f"❌ Celery: ошибка - {str(e)}")
        return False


async def test_interview_service():
    """Тест сервиса интервью (без LiveKit)"""
    print("\n🔍 Тестируем сервис интервью...")
    
    try:
        from app.services.interview_service import InterviewRoomService
        from app.core.database import get_db
        
        async for db in get_db():
            service = InterviewRoomService(db)
            
            # Тестируем генерацию токена (должен работать даже без LiveKit сервера)
            try:
                token = service.generate_access_token("test_room", "test_user")
                print("✅ Interview Service: генерация токенов работает")
                print(f"🎫 Тестовый токен сгенерирован (длина: {len(token)})")
            except Exception as e:
                print(f"⚠️  Interview Service: ошибка токена - {str(e)}")
            
            # Тестируем fallback план интервью
            fallback_plan = service._get_fallback_interview_plan()
            print("✅ Interview Service: fallback план работает")
            print(f"📋 Структура плана: {list(fallback_plan.keys())}")
            
            return True
            
    except Exception as e:
        print(f"❌ Interview Service: ошибка - {str(e)}")
        return False


def test_ai_agent_import():
    """Тест импорта AI агента"""
    print("\n🔍 Тестируем AI агента...")
    
    try:
        from ai_interviewer_agent import InterviewAgent
        
        # Тестовый план интервью
        test_plan = {
            "interview_structure": {
                "duration_minutes": 15,
                "greeting": "Привет! Тест интервью",
                "sections": [
                    {
                        "name": "Знакомство",
                        "duration_minutes": 5,
                        "questions": ["Расскажи о себе"]
                    },
                    {
                        "name": "Опыт",
                        "duration_minutes": 10,
                        "questions": ["Какой у тебя опыт?"]
                    }
                ]
            },
            "candidate_info": {
                "name": "Тестовый кандидат",
                "skills": ["Python"],
                "total_years": 2
            }
        }
        
        agent = InterviewAgent(test_plan)
        
        print("✅ AI Agent: импорт и инициализация работают")
        print(f"📊 Секций в плане: {len(agent.sections)}")
        print(f"🎯 Текущая секция: {agent.get_current_section().get('name')}")
        
        # Тестируем извлечение системных инструкций
        instructions = agent.get_system_instructions()
        print(f"📝 Инструкции сгенерированы (длина: {len(instructions)})")
        
        return True
        
    except Exception as e:
        print(f"❌ AI Agent: ошибка - {str(e)}")
        return False


def check_external_services():
    """Проверка внешних сервисов"""
    print("\n🔍 Проверяем внешние сервисы...")
    
    # Проверяем Milvus
    try:
        from rag.settings import settings
        response = requests.get(f"{settings.milvus_uri}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Milvus: сервер доступен")
        else:
            print("⚠️  Milvus: сервер недоступен")
    except Exception:
        print("❌ Milvus: сервер недоступен")
    
    # Проверяем LiveKit (если запущен)
    try:
        # LiveKit health check обычно на HTTP порту
        livekit_http_url = settings.livekit_url.replace("ws://", "http://").replace(":7880", ":7880")
        response = requests.get(livekit_http_url, timeout=2)
        print("✅ LiveKit: сервер запущен")
    except Exception:
        print("❌ LiveKit: сервер не запущен")
        print("💡 Для запуска LiveKit используйте Docker: docker run --rm -p 7880:7880 -p 7881:7881 livekit/livekit-server --dev")


async def run_all_tests():
    """Запуск всех тестов"""
    print("=== HR-AI System Testing ===")
    print("=" * 50)
    
    tests = [
        ("Database", test_database_connection),
        ("RAG System", test_rag_system),
        ("Redis", lambda: test_redis_connection()),
        ("Celery", test_celery_tasks),
        ("Interview Service", test_interview_service),
        ("AI Agent", lambda: test_ai_agent_import()),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results[test_name] = result
        except Exception as e:
            print(f"❌ {test_name}: критическая ошибка - {str(e)}")
            results[test_name] = False
    
    # Проверяем внешние сервисы
    check_external_services()
    
    # Итоговый отчет
    print("\n" + "=" * 50)
    print("📊 ИТОГОВЫЙ ОТЧЕТ")
    print("=" * 50)
    
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:20} {status}")
    
    print(f"\n🎯 Результат: {passed}/{total} тестов прошли успешно")
    
    if passed == total:
        print("🎉 Система готова к тестированию!")
        print_next_steps()
    else:
        print("⚠️  Некоторые компоненты требуют настройки")
        print_troubleshooting()


def print_next_steps():
    """Следующие шаги для полного тестирования"""
    print("\n📋 СЛЕДУЮЩИЕ ШАГИ:")
    print("1. Запустите FastAPI сервер: uvicorn app.main:app --reload")
    print("2. Запустите Celery worker: celery -A celery_worker.celery_app worker --loglevel=info")
    print("3. Загрузите тестовое резюме через /resume/upload")
    print("4. Проверьте генерацию плана интервью в базе данных")
    print("5. Для полного теста голосовых интервью потребуются:")
    print("   - API ключи Deepgram/Cartesia")
    print("   - LiveKit сервер")


def print_troubleshooting():
    """Устранение неисправностей"""
    print("\n🔧 УСТРАНЕНИЕ ПРОБЛЕМ:")
    print("• Redis не запущен: docker run -d -p 6379:6379 redis:alpine")
    print("• Milvus недоступен: проверьте настройки MILVUS_URI")  
    print("• RAG ошибки: проверьте OPENAI_API_KEY")
    print("• База данных: проверьте DATABASE_URL и запустите alembic upgrade head")


if __name__ == "__main__":
    asyncio.run(run_all_tests())