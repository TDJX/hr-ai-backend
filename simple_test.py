#!/usr/bin/env python3
"""Simple system test without Unicode characters"""

import asyncio
import sys
from pathlib import Path

# Add root directory to PYTHONPATH
sys.path.append(str(Path(__file__).parent))

async def test_database():
    """Test PostgreSQL connection"""
    print("Testing database connection...")
    
    try:
        from app.core.database import get_session as get_db
        from app.models.resume import Resume
        from sqlalchemy import select
        
        async for db in get_db():
            result = await db.execute(select(Resume).limit(1))
            resumes = result.scalars().all()
            
            print("PASS - Database connection successful")
            print(f"Found resumes: {len(resumes)}")
            return True
            
    except Exception as e:
        print(f"FAIL - Database error: {str(e)}")
        return False


async def test_rag():
    """Test RAG system"""
    print("\nTesting RAG system...")
    
    try:
        from rag.registry import registry
        from rag.llm.model import ResumeParser
        
        chat_model = registry.get_chat_model()
        parser = ResumeParser(chat_model)
        
        # Test resume text
        test_text = """
        John Doe
        Python Developer
        Experience: 3 years
        Skills: Python, Django, PostgreSQL
        Education: Computer Science
        """
        
        parsed_resume = parser.parse_resume_text(test_text)
        
        print("PASS - RAG system working")
        print(f"Parsed data keys: {list(parsed_resume.keys())}")
        
        return True
        
    except Exception as e:
        print(f"FAIL - RAG error: {str(e)}")
        return False


def test_redis():
    """Test Redis connection"""
    print("\nTesting Redis connection...")
    
    try:
        import redis
        from rag.settings import settings
        
        r = redis.Redis(
            host=settings.redis_cache_url,
            port=settings.redis_cache_port,
            db=settings.redis_cache_db
        )
        
        r.ping()
        print("PASS - Redis connection successful")
        return True
        
    except Exception as e:
        print(f"FAIL - Redis error: {str(e)}")
        print("TIP: Start Redis with: docker run -d -p 6379:6379 redis:alpine")
        return False


async def test_interview_service():
    """Test interview service"""
    print("\nTesting interview service...")
    
    try:
        from app.services.interview_service import InterviewRoomService
        from app.core.database import get_session as get_db
        
        async for db in get_db():
            service = InterviewRoomService(db)
            
            # Test token generation
            token = service.generate_access_token("test_room", "test_user")
            print(f"PASS - Token generated (length: {len(token)})")
            
            # Test fallback plan
            plan = service._get_fallback_interview_plan()
            print(f"PASS - Interview plan structure: {list(plan.keys())}")
            
            return True
            
    except Exception as e:
        print(f"FAIL - Interview service error: {str(e)}")
        return False


def test_ai_agent():
    """Test AI agent"""
    print("\nTesting AI agent...")
    
    try:
        from ai_interviewer_agent import InterviewAgent
        
        test_plan = {
            "interview_structure": {
                "duration_minutes": 15,
                "greeting": "Hello! Test interview",
                "sections": [
                    {
                        "name": "Introduction",
                        "duration_minutes": 5,
                        "questions": ["Tell me about yourself"]
                    }
                ]
            },
            "candidate_info": {
                "name": "Test Candidate",
                "skills": ["Python"],
                "total_years": 2
            }
        }
        
        agent = InterviewAgent(test_plan)
        
        print(f"PASS - AI Agent initialized with {len(agent.sections)} sections")
        print(f"Current section: {agent.get_current_section().get('name')}")
        
        return True
        
    except Exception as e:
        print(f"FAIL - AI Agent error: {str(e)}")
        return False


async def main():
    """Run all tests"""
    print("=" * 50)
    print("HR-AI SYSTEM TEST")
    print("=" * 50)
    
    tests = [
        ("Database", test_database),
        ("RAG System", test_rag),
        ("Redis", lambda: test_redis()),
        ("Interview Service", test_interview_service),
        ("AI Agent", lambda: test_ai_agent()),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"CRITICAL ERROR in {test_name}: {str(e)}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("TEST RESULTS")
    print("=" * 50)
    
    passed = 0
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"{test_name:20} {status}")
        if result:
            passed += 1
    
    total = len(results)
    print(f"\nRESULT: {passed}/{total} tests passed")
    
    if passed == total:
        print("\nSYSTEM READY FOR TESTING!")
        print("Next steps:")
        print("1. Start FastAPI: uvicorn app.main:app --reload")
        print("2. Start Celery: celery -A celery_worker.celery_app worker --loglevel=info") 
        print("3. Upload test resume via /resume/upload")
        print("4. Check interview plan generation")
    else:
        print("\nSOME COMPONENTS NEED SETUP")
        print("Check error messages above for troubleshooting")


if __name__ == "__main__":
    asyncio.run(main())