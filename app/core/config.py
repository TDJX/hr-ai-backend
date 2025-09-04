from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://tdjx:1309@localhost:5432/hr_ai"

    # Redis Configuration (for Celery and caching)
    redis_cache_url: str = "localhost"
    redis_cache_port: int = 6379
    redis_cache_db: int = 0

    # Milvus Vector Database
    milvus_uri: str = "http://localhost:19530"
    milvus_collection: str = "candidate_profiles"

    # S3 Storage
    s3_endpoint_url: str = "https://s3.selcdn.ru"
    s3_access_key_id: str
    s3_secret_access_key: str
    s3_bucket_name: str
    s3_region: str = "ru-1"

    # LLM API Keys
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_embeddings_model: str = "text-embedding-3-small"

    # AI Agent API Keys (for voice interviewer)
    deepgram_api_key: str | None = None
    cartesia_api_key: str | None = None
    elevenlabs_api_key: str | None = None
    resemble_api_key: str | None = None

    # LiveKit Configuration
    livekit_url: str = "ws://localhost:7880"
    livekit_api_key: str = "devkey"
    livekit_api_secret: str = "devkey_secret_32chars_minimum_length"

    # App Configuration
    app_env: str = "development"
    debug: bool = True

    class Config:
        env_file = ".env"


settings = Settings()
