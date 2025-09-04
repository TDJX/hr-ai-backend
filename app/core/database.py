from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import create_engine
from sqlmodel import SQLModel

from .config import settings

# Async engine для FastAPI
async_engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_pre_ping=True,
)

async_session = sessionmaker(
    async_engine,
    expire_on_commit=False,
    class_=AsyncSession,
)

# Sync engine для Celery и других синхронных операций
sync_engine = create_engine(
    settings.database_url.replace("asyncpg", "psycopg2"),
    echo=settings.debug,
    future=True,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_pre_ping=True,
    pool_recycle=3600,
)

sync_session = sessionmaker(
    bind=sync_engine,
    expire_on_commit=False,
    class_=Session,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Async session для FastAPI DI"""
    async with async_session() as session:
        yield session


def get_sync_session() -> Generator[Session, None, None]:
    """Sync session для Celery и других синхронных операций"""
    with sync_session() as session:
        yield session


async def create_db_and_tables():
    """Создать таблицы в БД"""
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)