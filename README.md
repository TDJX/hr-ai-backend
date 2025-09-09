# HR AI Backend

Система автоматического проведения собеседований с помощью ИИ агента. Включает парсинг резюме, проведение голосовых интервью через LiveKit, анализ результатов и генерацию PDF отчетов.

## 🚀 Основной функционал

### 📄 Управление резюме
- **Загрузка и парсинг резюме** в форматах PDF, DOCX
- **Автоматическое извлечение данных**: ФИО, навыки, опыт работы, образование
- **Генерация плана интервью** на основе содержания резюме
- **Поиск и фильтрация** резюме по различным критериям
- **Векторный поиск** с использованием Milvus для семантического поиска

### 🎯 Управление вакансиями
- **Создание и редактирование** вакансий
- **Парсинг вакансий** из файлов (txt, docx)
- **Автоматическое сопоставление** резюме с вакансиями
- **Ранжирование кандидатов** по соответствию вакансии

### 🎤 AI-собеседования
- **Голосовые интервью** с использованием LiveKit и OpenAI
- **Адаптивный AI-интервьюер "Стефани"** с русскоязычным интерфейсом
- **Автоматическая генерация вопросов** под конкретного кандидата
- **Реальное время** распознавание речи и синтез голоса
- **Трекинг времени и прогресса** интервью

### 📊 Анализ и отчетность
- **Автоматический анализ интервью** с помощью GPT-4
- **Комплексная оценка** по 5 критериям:
  - Технические навыки
  - Релевантность опыта
  - Коммуникативные навыки
  - Решение проблем
  - Культурное соответствие
- **Генерация PDF отчетов** с детальной оценкой
- **Рекомендации** по найму (strongly_recommend/recommend/consider/reject)
- **Аналитика по вакансиям** и статистика кандидатов

### 🔧 Администрирование
- **Мониторинг системы** и активных процессов
- **Управление AI агентами** (запуск/остановка)
- **Аналитические панели** с метриками
- **Логирование и отладка** всех процессов

## 🏗️ Архитектура

### Основные компоненты

**FastAPI приложение** (`app/`):
- `main.py` - точка входа с middleware и настройкой роутеров
- `routers/` - API эндпоинты по доменам (resume, interview, vacancy, admin)
- `models/` - SQLModel схемы базы данных с отношениями
- `services/` - бизнес-логика для обработки сложных операций
- `repositories/` - слой доступа к данным с использованием SQLModel/SQLAlchemy

**Фоновая обработка** (`celery_worker/`):
- `celery_app.py` - настройка Celery с Redis backend
- `tasks.py` - асинхронные задачи для парсинга резюме и анализа
- `interview_analysis_task.py` - специализированная задача для анализа интервью

**AI система интервью**:
- `ai_interviewer_agent.py` - голосовой AI агент на базе LiveKit
- `app/services/agent_manager.py` - singleton менеджер для управления агентами
- Агент работает как единый процесс, обрабатывая одно интервью за раз
- Межпроцессное взаимодействие через JSON файлы команд
- Автоматический запуск/остановка с жизненным циклом FastAPI

**RAG система** (`rag/`):
- `vector_store.py` - интеграция с векторной БД Milvus для поиска резюме
- `llm/model.py` - интеграция с OpenAI GPT для парсинга и планирования интервью
- `service/model.py` - оркестрация RAG сервисов

### База данных

**Ключевые модели**:
- `Resume` - резюме кандидатов с статусами парсинга и планами интервью
- `InterviewSession` - сессии LiveKit с трекингом AI агента
- `InterviewReport` - детальные отчеты по интервью с оценками
- `Vacancy` - вакансии с требованиями и описанием
- `Session` - управление пользовательскими сессиями через cookies

**Статусы**:
- `ResumeStatus`: pending → parsing → parsed → interview_scheduled → interviewed
- `InterviewStatus`: created → active → completed/failed
- `RecommendationType`: strongly_recommend/recommend/consider/reject

## 🛠️ Технологический стек

- **Backend**: FastAPI, Python 3.11+
- **База данных**: PostgreSQL с asyncpg
- **Кэш и брокер**: Redis
- **Векторная БД**: Milvus (опционально, есть fallback)
- **Файловое хранилище**: S3-совместимое хранилище
- **AI/ML**: OpenAI GPT-4, Whisper STT
- **Голосовые технологии**: LiveKit, Deepgram, Cartesia, ElevenLabs
- **Очереди**: Celery для асинхронных задач
- **PDF генерация**: Playwright (заменил WeasyPrint)
- **Контейнеризация**: Docker для некоторых сервисов

## 📦 Установка и запуск

### Предварительные требования

1. **Python 3.11+** с uv пакетным менеджером
2. **PostgreSQL** (локально или в Docker)
3. **Redis** (для Celery и кэширования)
4. **Milvus** (опционально, для векторного поиска)
5. **S3-совместимое хранилище** (MinIO или AWS S3)

### 1. Клонирование и зависимости

```bash
git clone <repository-url>
cd hr-ai-backend

# Установка зависимостей через uv
uv sync

# Установка Playwright браузеров для PDF генерации
uv run playwright install chromium
```

### 2. Настройка окружения

Создайте файл `.env` на основе `.env.example`:

```bash
cp .env.example .env
```

Заполните основные переменные:

```env
# База данных
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/hr_ai_backend

# Redis
REDIS_URL=redis://localhost:6379/0

# OpenAI API
OPENAI_API_KEY=your-openai-api-key

# LiveKit (для голосовых интервью)
LIVEKIT_URL=ws://localhost:7880
LIVEKIT_API_KEY=your-livekit-key
LIVEKIT_API_SECRET=your-livekit-secret

# S3 хранилище
S3_ENDPOINT_URL=http://localhost:9000
S3_ACCESS_KEY_ID=minioadmin
S3_SECRET_ACCESS_KEY=minioadmin
S3_BUCKET_NAME=hr-ai-files

# Milvus (опционально)
MILVUS_URI=http://localhost:19530
```

### 3. Запуск сервисов

```bash
# 1. Запуск Redis
docker run -d --name redis -p 6379:6379 redis

# 2. Запуск LiveKit сервера (для интервью)
docker run -d --name livekit \
  -p 7880:7880 -p 7881:7881 \
  livekit/livekit-server --dev
```

### 4. Миграции базы данных

```bash
# Применить миграции
uv run alembic upgrade head

# Создать новую миграцию (при изменении моделей)
uv run alembic revision --autogenerate -m "описание изменений"
```

### 5. Запуск приложения

```bash
# FastAPI сервер
uv run fastapi dev main.py

# Celery worker (в отдельном терминале)
uv run celery -A celery_worker.celery_app worker --loglevel=info
```

### База данных

```bash
# Новая миграция
uv run alembic revision --autogenerate -m "описание"

# Применить миграции
uv run alembic upgrade head

```

## 🎯 Основные API эндпоинты

### Резюме
- `POST /api/v1/resume/upload` - загрузка резюме
- `GET /api/v1/resume/` - список резюме с фильтрацией
- `GET /api/v1/resume/{id}` - получение резюме
- `DELETE /api/v1/resume/{id}` - удаление резюме

### Вакансии  
- `POST /api/v1/vacancy/` - создание вакансии
- `GET /api/v1/vacancy/` - список вакансий
- `POST /api/v1/vacancy/parse` - парсинг вакансии из файла

### Интервью
- `POST /api/v1/interview/{resume_id}/validate` - валидация готовности к интервью
- `POST /api/v1/interview/{resume_id}/token` - получение токена LiveKit
- `GET /api/v1/interview/{resume_id}/status` - статус интервью

### Анализ и отчеты
- `POST /api/v1/analysis/interview-report/{resume_id}` - запуск анализа интервью
- `GET /api/v1/analysis/report/{resume_id}` - получение отчета
- `POST /api/v1/analysis/generate-pdf/{resume_id}` - генерация PDF отчета
- `GET /api/v1/analysis/pdf-report/{resume_id}` - скачивание PDF

## 🔄 Рабочий процесс

### 1. Обработка резюме
1. Загрузка файла через `/api/v1/resume/upload`
2. Celery задача извлекает текст и парсит данные через OpenAI
3. Генерируется план интервью под кандидата
4. Создаются векторные эмбеддинги для поиска
5. Статус обновляется через enum: `parsing` → `parsed`

### 2. Проведение интервью
1. Валидация готовности через `/api/v1/interview/{id}/validate`
2. Получение токена LiveKit для подключения
3. AI агент автоматически назначается на сессию
4. Проведение голосового интервью в реальном времени
5. Сохранение диалога и автоматическое завершение
6. Статус резюме: `interview_scheduled` → `interviewed`

### 3. Анализ результатов
1. После завершения интервью запускается анализ через HTTP fallback
2. GPT-5-mini анализирует диалог по 5 критериям с оценками 0-100
3. Создается `InterviewReport` с детальной оценкой
4. Генерируется рекомендация: `strongly_recommend`/`recommend`/`consider`/`reject`
5. При необходимости создается PDF отчет через Playwright

## 🐛 Отладка и мониторинг

### Логирование
- Все процессы логируются с детальным трейсингом
- AI агент: отдельный лог файл `ai_agent.log`
- Celery worker: стандартный вывод с уровнем INFO
- FastAPI: встроенное логирование с middleware

### Частые проблемы
1. **Агент не запускается**: проверьте LiveKit сервер и API ключи
2. **Celery задачи висят**: проверьте подключение к Redis
3. **PDF не генерируется**: убедитесь что Playwright браузеры установлены
4. **Парсинг не работает**: проверьте OpenAI API ключ и квоты


💡 **Примечание**: Система в активной разработке. AI агент работает как singleton (одно интервью за раз) - это ограничение хакатона, в продакшене можно масштабировать на несколько агентов.