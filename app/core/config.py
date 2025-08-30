from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/hr_ai_db"
    
    s3_endpoint_url: str = "https://s3.selcdn.ru"
    s3_access_key_id: str
    s3_secret_access_key: str
    s3_bucket_name: str
    s3_region: str = "ru-1"
    
    app_env: str = "development"
    debug: bool = True
    
    class Config:
        env_file = ".env"


settings = Settings()