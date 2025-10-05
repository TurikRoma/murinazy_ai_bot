from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)
from typing import AsyncGenerator

from config.settings import settings


engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(
    engine, 
    expire_on_commit=False, 
    class_=AsyncSession
)


def create_session_pool():
    """Создает и возвращает пул асинхронных сессий для работы с базой данных."""
    return async_session_maker


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Генератор для получения сессии БД"""
    async with async_session_maker() as session:
        yield session
