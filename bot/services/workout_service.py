import asyncio
import logging
from datetime import date, datetime, timedelta, time

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.requests import user_requests, exercise_requests, schedule_requests
from bot.requests.workout_requests import save_weekly_plan
from bot.scheduler import scheduler, send_workout_notification
from bot.services.llm_service import llm_service
from bot.schemas.workout import PlanSummary
from bot.utils.workout_utils import calculate_effective_training_week


class WorkoutService:
    def __init__(self, bot: Bot, session_pool: async_sessionmaker):
        self.bot = bot
        self.session_pool = session_pool

    async def create_and_schedule_weekly_workout(
        self, session: AsyncSession, telegram_id: int
    ) -> tuple[PlanSummary, datetime | None] | None:
        """
        Главный метод: генерирует, сохраняет и планирует недельный план тренировок.
        Возвращает (plan_summary, datetime следующей тренировки) или None.
        """
        user = await user_requests.get_user_by_telegram_id(session, telegram_id)
        if not user:
            logging.error(f"User with telegram_id {telegram_id} not found.")
            return None

        # 1. Вычисляем "эффективную" неделю для LLM
        effective_week = calculate_effective_training_week(
            user.current_training_week or 1, user.fitness_level.value
        )

        # 2. Генерация плана через LLM с retry-логикой
        plan = None
        for attempt in range(2):
            try:
                all_exercises = await exercise_requests.get_exercises_by_equipment(
                    session, user.equipment_type
                )
                plan = await llm_service.generate_workout_plan(
                    user, all_exercises, effective_week
                )
                logging.info(f"LLM generated plan for user {user.telegram_id}: {plan.model_dump_json(indent=2)}")
                break  # Успешная генерация, выходим из цикла
            except Exception as e:
                logging.error(f"LLM workout generation failed on attempt {attempt + 1}: {e}")
                if attempt == 0:
                    await asyncio.sleep(1)  # Пауза перед повторной попыткой

        if not plan:
            # Если не удалось сгенерировать, возвращаем None, обработчик отправит сообщение
            return None

        # 3. Определение дат тренировок
        workout_dates = await self._calculate_workout_datetimes(session, user.id, len(plan.workout_plan))
        if not workout_dates:
            return None # Если не удалось рассчитать даты, выходим

        # FIX: Убедимся, что количество сессий не превышает количество рассчитанных дат.
        if len(plan.workout_plan) > len(workout_dates):
            logging.warning(
                f"LLM сгенерировал {len(plan.workout_plan)} сессий, но доступно только {len(workout_dates)} "
                f"слотов. План будет урезан."
            )
            plan.workout_plan = plan.workout_plan[:len(workout_dates)]

        # 4. Сохранение плана и дат в БД
        workouts = await save_weekly_plan(session, user.id, plan, workout_dates)
        if not workouts:
            return None # Если не удалось сохранить, выходим

        # 5. Инкремент недели пользователя
        await user_requests.increment_user_training_week(session, user.id)
        
        # 6. Планирование уведомлений
        logging.info(f"Начинаю планирование {len(workouts)} тренировок для пользователя {user.telegram_id}")
        for workout in workouts:
            run_datetime = workout.planned_date
            # Не планируем задачи в прошлом
            if run_datetime > datetime.now():
                try:
                    scheduler.add_job(
                        send_workout_notification,
                        trigger="date",
                        run_date=run_datetime,
                        args=[self.bot, user.telegram_id, workout.id, self.session_pool],
                        id=f"workout_{workout.id}",
                        replace_existing=True,
                    )
                    logging.info(
                        f"Успешно запланирована тренировка #{workout.id} на {run_datetime} "
                        f"для пользователя {user.telegram_id}"
                    )
                except Exception as e:
                    logging.error(
                        f"Ошибка планирования тренировки #{workout.id} для пользователя {user.telegram_id}: {e}",
                        exc_info=True
                    )
            else:
                logging.warning(
                    f"Пропуск планирования тренировки #{workout.id} для пользователя {user.telegram_id}, "
                    f"так как ее время ({run_datetime}) уже в прошлом."
                )

        # 7. Возвращаем summary и дату ближайшей тренировки
        next_workout_date = workouts[0].planned_date if workouts else None
        return plan.plan_summary, next_workout_date

    async def _calculate_workout_datetimes(
        self, session: AsyncSession, user_id: int, num_workouts: int
    ) -> list[datetime]:
        """
        Вычисляет точные дату и время для N тренировок на основе расписания пользователя.
        Сначала ищет слоты на текущей неделе. Если их нет, ищет на следующей.
        """
        user_schedule = await schedule_requests.get_user_schedule(session, user_id)
        now = datetime.now()

        if not user_schedule:
            # Новая логика: планируем только до конца текущей недели.
            # Понедельник - 0, Воскресенье - 6
            today_weekday = now.weekday()
            # +1 чтобы включить сегодняшний день
            days_left_in_week = 6 - today_weekday + 1

            # Планируем не больше тренировок, чем запрошено и чем дней осталось в неделе
            workouts_to_schedule = min(num_workouts, days_left_in_week)

            # Генерируем даты на оставшиеся дни, начиная с СЕГОДНЯ
            return [now + timedelta(days=i) + timedelta(minutes=1) for i in range(workouts_to_schedule)]

        weekday_map = {
            "понедельник": 0, "вторник": 1, "среда": 2, "четверг": 3,
            "пятница": 4, "суббота": 5, "воскресенье": 6
        }
        slots = sorted(
            [(weekday_map[s.day.value], s.notification_time) for s in user_schedule]
        )

        def find_slots(start_offset, days_to_check, current_dates):
            """Ищет доступные слоты в заданном диапазоне дней."""
            for day_offset in range(start_offset, start_offset + days_to_check):
                if len(current_dates) >= num_workouts:
                    break
                check_date = (now + timedelta(days=day_offset)).date()
                for wday, time_obj in slots:
                    if wday == check_date.weekday():
                        potential_dt = datetime.combine(check_date, time_obj)
                        if potential_dt > now:
                            current_dates.append(potential_dt)
            return current_dates

        # 1. Ищем слоты на текущей неделе
        today_weekday = now.weekday()
        days_to_check_current_week = 7 - today_weekday
        workout_datetimes = find_slots(0, days_to_check_current_week, [])

        # 2. Если на текущей неделе ничего не найдено, ищем на следующей
        if not workout_datetimes:
            start_offset_next_week = days_to_check_current_week
            workout_datetimes = find_slots(start_offset_next_week, 7, [])
        
        # Сортируем на случай, если в один день несколько слотов, и обрезаем до нужного количества
        workout_datetimes.sort()
        return workout_datetimes[:num_workouts]
