import asyncio
import sys
from pathlib import Path

# Добавляем корневую папку проекта в sys.path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete

from database.connection import async_session_maker
from database.models import Exercise


async def clear_exercises():
    """
    Полностью очищает таблицу exercises в базе данных.
    """
    async with async_session_maker() as session:
        await session.execute(delete(Exercise))
        await session.commit()
        print("Таблица 'exercises' была успешно очищена.")


if __name__ == "__main__":
    asyncio.run(clear_exercises())
