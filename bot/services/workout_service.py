import asyncio
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from bot.config.settings import settings
from bot.requests.workout_requests import get_last_workout_date, create_full_workout
from bot.requests.exercise_requests import get_exercises_by_equipment, get_exercises_by_names
from bot.services.llm_service import llm_service
from database.models import User, Workout


class WorkoutCooldownError(Exception):
    def __init__(self, message="Вы можете запросить новую тренировку не раньше, чем через 12 часов."):
        self.message = message
        super().__init__(self.message)


class WorkoutService:
    async def create_new_workout_plan(self, session: AsyncSession, user: User) -> Workout:
        last_workout_time = await get_last_workout_date(session, user.id)
        if last_workout_time and (datetime.utcnow() - last_workout_time) < timedelta(
                hours=settings.WORKOUT_COOLDOWN_HOURS):
            raise WorkoutCooldownError()

        # 1. Получение доступных упражнений
        exercises = await get_exercises_by_equipment(
            session, user.equipment_type
        )
        if not exercises:
            raise ValueError("В базе данных нет упражнений для вашего типа оборудования.")

        # 2. Генерация плана с помощью LLM
        llm_plan = await llm_service.generate_workout_plan(user, list(exercises))
        
        # 3. Получение ID упражнений из БД по их названиям
        exercise_names = [
            ex.name for s in llm_plan.sessions for ex in s.exercises
        ]
        exercises_from_db = await get_exercises_by_names(
            session, exercise_names
        )
        exercises_map = {ex.name: ex for ex in exercises_from_db}

        # 4. Сохранение полной тренировки в БД
        workout_db = await create_full_workout(
            session, user, llm_plan, exercises_map
        )
        return workout_db

    def format_workout_message(self, workout: Workout) -> str:
        """Форматирует красивый текстовый ответ с программой тренировок."""
        response_text = "🔥 **Ваша новая программа тренировок готова!**\n\n"
        
        session_exercises = {}
        for we in workout.workout_exercises:
            # Предполагаем, что 'session_day' хранится в WorkoutExercise
            day = we.order // 10  # Примерная логика для определения дня
            if day not in session_exercises:
                session_exercises[day] = []
            session_exercises[day].append(we)

        for day, exercises in sorted(session_exercises.items()):
            response_text += f"**День {day}**\n"
            for we in sorted(exercises, key=lambda x: x.order):
                response_text += (
                    f"  - {we.exercise.name}: {we.sets} подхода по {we.reps} повторений\n"
                )
            response_text += "\n"

        return response_text


workout_service = WorkoutService()
