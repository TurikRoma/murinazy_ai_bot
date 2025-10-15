import datetime
from typing import List, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import Workout, WorkoutExercise, Exercise, User
from bot.schemas.workout import LLMWorkoutPlan


async def get_last_workout_for_user(
    session: AsyncSession, user_id: int
) -> Workout | None:
    """Получает последнюю по дате создания тренировку пользователя."""
    stmt = (
        select(Workout)
        .where(Workout.user_id == user_id)
        .order_by(Workout.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalars().first()


async def get_last_workout_date(session: AsyncSession, user_id: int) -> datetime.datetime | None:
    """Возвращает только дату последней тренировки пользователя."""
    stmt = select(Workout.created_at).where(Workout.user_id == user_id).order_by(Workout.created_at.desc()).limit(1)
    result = await session.execute(stmt)
    return result.scalars().first()


async def create_workout_with_exercises(session: AsyncSession, user_id: int, workout_plan: "LLMWorkoutPlan") -> Workout:
    """Создает новую тренировку и связанные с ней упражнения."""
    
    # 1. Создаем объект тренировки
    new_workout = Workout(user_id=user_id)
    session.add(new_workout)
    await session.flush() # Получаем workout.id до коммита

    # 2. Создаем упражнения для тренировки
    workout_exercises = []
    order_counter = 1
    for session_plan in workout_plan.sessions:
        for exercise_plan in session_plan.exercises:
            # Находим упражнение в БД по имени
            stmt = select(Exercise).where(Exercise.name == exercise_plan.name)
            result = await session.execute(stmt)
            exercise = result.scalars().first()
            if not exercise:
                # Пропускаем, если упражнение не найдено. В идеале - логировать.
                continue

            we = WorkoutExercise(
                workout_id=new_workout.id,
                exercise_id=exercise.id,
                session_day=session_plan.day,
                order=order_counter,
                sets=exercise_plan.sets,
                reps=exercise_plan.reps,
            )
            workout_exercises.append(we)
            order_counter += 1
            
    session.add_all(workout_exercises)
    await session.commit()

    # Перезагружаем тренировку с упражнениями для возврата
    await session.refresh(new_workout, attribute_names=["workout_exercises"])
    return new_workout


async def create_full_workout(
    session: AsyncSession,
    user: User,
    plan: LLMWorkoutPlan,
    exercises_map: dict[str, Exercise],
) -> Workout:
    """
    Создает полную тренировку с упражнениями в одной транзакции.
    """
    # 1. Создаем основную запись о тренировке
    new_workout = Workout(user_id=user.id)
    session.add(new_workout)
    await session.flush()  # Получаем ID для связи

    # 2. Создаем записи для каждого упражнения в плане
    workout_exercises_to_add = []
    order = 1
    for session_plan in plan.sessions:
        for ex_plan in session_plan.exercises:
            exercise_db = exercises_map.get(ex_plan.name)
            if not exercise_db:
                # В идеале здесь нужно логировать ошибку,
                # так как LLM вернула упражнение, которого нет в нашей БД
                continue

            workout_exercise = WorkoutExercise(
                workout_id=new_workout.id,
                exercise_id=exercise_db.id,
                sets=ex_plan.sets,
                reps=ex_plan.reps,  # В модели это Integer, нужна будет адаптация
                order=order,
            )
            workout_exercises_to_add.append(workout_exercise)
            order += 1

    session.add_all(workout_exercises_to_add)
    await session.commit()

    # Загружаем созданную тренировку с упражнениями для возврата
    stmt = (
        select(Workout)
        .where(Workout.id == new_workout.id)
        .options(selectinload(Workout.workout_exercises).selectinload(WorkoutExercise.exercise))
    )
    result = await session.execute(stmt)
    return result.scalars().one()
