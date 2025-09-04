# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Development Commands

### Application Startup
```bash
# Start FastAPI server
uvicorn app.main:app --reload --port 8000

# Start Celery worker (required for resume processing)
celery -A celery_worker.celery_app worker --loglevel=info

# Start LiveKit server (for voice interviews)
docker run --rm -p 7880:7880 -p 7881:7881 livekit/livekit-server --dev
```

### Database Management
```bash
# Run database migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"
```

### Code Quality
```bash
# Format code and fix imports
ruff format .

# Lint and auto-fix issues
ruff check . --fix

# Type checking
mypy .
```

### Testing
```bash
# Run basic system tests
python simple_test.py

# Run comprehensive tests
python test_system.py

# Test agent integration
python test_agent_integration.py

# Run pytest suite
pytest
```

## Architecture Overview

### Core Components

**FastAPI Application** (`app/`):
- `main.py`: Application entry point with middleware and router configuration
- `routers/`: API endpoints organized by domain (resume, interview, vacancy, admin)
- `models/`: SQLModel database schemas with enums and relationships
- `services/`: Business logic layer handling complex operations
- `repositories/`: Data access layer using SQLModel/SQLAlchemy

**Background Processing** (`celery_worker/`):
- `celery_app.py`: Celery configuration with Redis backend
- `tasks.py`: Asynchronous tasks for resume parsing and interview analysis
- `interview_analysis_task.py`: Specialized task for processing interview results

**AI Interview System**:
- `ai_interviewer_agent.py`: LiveKit-based voice interview agent using OpenAI, Deepgram, and Cartesia
- `app/services/agent_manager.py`: Singleton manager for controlling the AI agent lifecycle
- Agent runs as a single process, handling one interview at a time (hackathon limitation)
- Inter-process communication via JSON command files
- Automatic startup/shutdown with FastAPI application lifecycle

**RAG System** (`rag/`):
- `vector_store.py`: Milvus vector database integration for resume search
- `llm/model.py`: OpenAI GPT integration for resume parsing and interview plan generation
- `service/model.py`: RAG service orchestration

### Database Schema

**Key Models**:
- `Resume`: Candidate resumes with parsing status, interview plans, and file storage
- `InterviewSession`: LiveKit rooms with AI agent process tracking
- `Vacancy`: Job postings with requirements and descriptions
- `Session`: User session management with cookie-based tracking

**Status Enums**:
- `ResumeStatus`: pending → parsing → parsed → interview_scheduled → interviewed
- `InterviewStatus`: created → active → completed/failed

### External Dependencies

**Required Services**:
- PostgreSQL: Primary database with asyncpg driver
- Redis: Celery broker and caching layer
- Milvus: Vector database for semantic search (optional, has fallbacks)
- S3-compatible storage: Resume file storage

**API Keys**:
- OpenAI: Required for resume parsing and LLM operations
- Deepgram/Cartesia/ElevenLabs: Optional voice services (has fallbacks)
- LiveKit credentials: For interview functionality

## Development Workflow

### Resume Processing Flow
1. File upload via `/api/v1/resume/upload`
2. Celery task processes file and extracts text
3. OpenAI parses resume data and generates interview plan
4. Vector embeddings stored in Milvus for search
5. Status updates tracked through enum progression

### Interview System Flow
1. AI agent starts automatically with FastAPI application
2. Validate resume readiness via `/api/v1/interview/{id}/validate`
3. Check agent availability (singleton, one interview at a time)
4. Generate LiveKit token via `/api/v1/interview/{id}/token`
5. Assign interview session to agent via command files
6. Conduct real-time voice interview through LiveKit
7. Agent monitors for end commands or natural completion
8. Session cleanup and agent returns to idle state

### Configuration Management
- Settings via `app/core/config.py` with Pydantic BaseSettings
- Environment variables loaded from `.env` file (see `.env.example`)
- Database URLs and API keys configured per environment

## Important Notes

- AI agent runs as a singleton process, handling one interview at a time
- Agent lifecycle is managed automatically with FastAPI startup/shutdown
- Interview sessions require LiveKit server to be running
- Agent communication happens via JSON files (agent_commands.json, session_metadata_*.json)
- Resume parsing is asynchronous and status should be checked via polling
- Vector search gracefully degrades if Milvus is unavailable
- Session management uses custom middleware with cookie-based tracking

## Agent Management API

```bash
# Check agent status
GET /api/v1/admin/agent/status

# Start/stop/restart agent manually
POST /api/v1/admin/agent/start
POST /api/v1/admin/agent/stop
POST /api/v1/admin/agent/restart
```