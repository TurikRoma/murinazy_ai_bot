from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select
from sqlalchemy.future import select
from typing import List, Sequence

from database.models import Exercise, EquipmentTypeEnum
from bot.schemas.exercise import ExerciseCreate


async def clear_exercises(session: AsyncSession) -> None:
    """Удаляет все упражнения из базы данных."""
    await session.execute(delete(Exercise))
    await session.commit()


async def add_exercises_bulk(
    session: AsyncSession, exercises: list[ExerciseCreate]
) -> None:
    """Добавляет несколько упражнений в базу данных."""
    exercise_objects = [Exercise(**ex.model_dump()) for ex in exercises]
    session.add_all(exercise_objects)
    await session.commit()


async def get_exercises_by_equipment(
    session: AsyncSession, equipment_type: EquipmentTypeEnum
) -> Sequence[Exercise]:
    """Получает все упражнения для указанного типа оборудования."""
    stmt = select(Exercise).where(Exercise.equipment_type == equipment_type)
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_exercises_by_names(
    session: AsyncSession, names: List[str]
) -> Sequence[Exercise]:
    """Получает упражнения по списку названий."""
    stmt = select(Exercise).where(Exercise.name.in_(names))
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_exercise_by_name(
    session: AsyncSession, name: str
) -> Exercise | None:
    """Получает одно упражнение по его точному названию."""
    stmt = select(Exercise).where(Exercise.name == name)
    result = await session.execute(stmt)
    return result.scalars().first()
