from celery import Celery

from rag.settings import settings

celery_app = Celery(
    "hr_ai_backend",
    broker=f"redis://{settings.redis_cache_url}:{settings.redis_cache_port}/{settings.redis_cache_db}",
    backend=f"redis://{settings.redis_cache_url}:{settings.redis_cache_port}/{settings.redis_cache_db}",
    include=["celery_worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
