import datetime
from typing import List, Sequence
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import Workout, WorkoutExercise, Exercise, User, WorkoutStatusEnum
from bot.schemas.workout import LLMWorkoutPlan
from bot.requests.exercise_requests import get_exercise_by_name



async def get_next_workout_for_user(
    session: AsyncSession, user_id: int
) -> Workout | None:
    """Получает следующую по дате планирования тренировку пользователя."""
    stmt = (
        select(Workout)
        .where(Workout.user_id == user_id, Workout.planned_date > datetime.datetime.now(), Workout.status == WorkoutStatusEnum.planned)
        .order_by(Workout.planned_date.asc())
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


async def save_weekly_plan(
    session: AsyncSession,
    user_id: int,
    plan: LLMWorkoutPlan,
    workout_dates: list[datetime],
) -> list[Workout]:
    """
    Сохраняет сгенерированный недельный план тренировок в БД.
    """
    created_workouts = []
    # Используем `workout_plan` вместо `sessions`
    for idx, day_plan in enumerate(plan.workout_plan):
        # Если дат меньше, чем сгенерировано тренировок, прекращаем сохранение
        if idx >= len(workout_dates):
            break

        # Создаем саму тренировку
        workout = Workout(
            user_id=user_id,
            planned_date=workout_dates[idx],
            warm_up=day_plan.warm_up,
            cool_down=day_plan.cool_down,
        )
        session.add(workout)
        await session.flush()  # Получаем ID тренировки

        # Добавляем упражнения к тренировке
        for exercise_data in day_plan.exercises:
            # Имя упражнения теперь в `exercise_name`
            exercise = await get_exercise_by_name(session, exercise_data.exercise_name)
            if exercise:
                workout_exercise = WorkoutExercise(
                    workout_id=workout.id,
                    exercise_id=exercise.id,
                    sets=exercise_data.sets,
                    reps=exercise_data.reps,
                    order=exercise_data.order,  # Сохраняем порядок из LLM
                )
                session.add(workout_exercise)
        created_workouts.append(workout)

    await session.commit()
    return created_workouts


async def get_workout_with_exercises(
    session: AsyncSession, workout_id: int
) -> Workout | None:
    """
    Получает тренировку со всеми связанными упражнениями.
    """
    stmt = (
        select(Workout)
        .where(Workout.id == workout_id)
        .options(selectinload(Workout.workout_exercises).selectinload(WorkoutExercise.exercise))
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_future_planned_workouts(session: AsyncSession) -> Sequence[Workout]:
    """
    Получает все запланированные тренировки, которые еще не начались.
    """
    stmt = (
        select(Workout)
        .where(
            Workout.status == WorkoutStatusEnum.planned,
            Workout.planned_date > datetime.datetime.now(),
        )
        .options(selectinload(Workout.user))
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def update_workout_status(
    session: AsyncSession, workout_id: int, status: WorkoutStatusEnum
) -> Workout | None:
    """Обновляет статус тренировки по ее ID."""
    workout = await session.get(Workout, workout_id)
    if workout:
        workout.status = status
        await session.commit()
        await session.refresh(workout)
    return workout
