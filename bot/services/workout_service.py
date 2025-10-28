import asyncio
import logging
from datetime import date, datetime, timedelta, time

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.requests import user_requests, exercise_requests, schedule_requests
from bot.requests.workout_requests import (
    save_weekly_plan,
    get_exercises_from_last_workouts,
    get_latest_planned_date,
)
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

        # 1. Вычисляем "эффективную" неделю для LLM.
        # Мы всегда генерируем план НА СЛЕДУЮЩУЮ неделю, поэтому добавляем +1.
        # Если current_training_week is None (самый первый запуск), считаем, что текущая неделя 0.
        next_week = (user.current_training_week or 0) + 1
        effective_week = calculate_effective_training_week(
            next_week, user.fitness_level.value
        )

        # 2. Генерация плана через LLM с retry-логикой
        plan = None
        for attempt in range(2):
            try:
                if effective_week == 1:
                    # Начало нового цикла: ищем новые упражнения
                    all_exercises = await exercise_requests.get_exercises_by_equipment(
                        session, user.equipment_type
                    )
                    banned_exercises = await get_exercises_from_last_workouts(
                        session, user.id, user.workout_frequency or 1
                    )
                    plan = await llm_service.generate_workout_plan(
                        user=user,
                        effective_training_week=effective_week,
                        available_exercises=all_exercises,
                        banned_exercises=banned_exercises,
                    )
                else:
                    # Середина цикла: используем те же упражнения
                    fixed_exercises = await get_exercises_from_last_workouts(
                        session, user.id, user.workout_frequency or 1
                    )
                    if not fixed_exercises:
                        logging.error(
                            f"Не найдены упражнения для пользователя {user.id} в середине цикла. "
                            f"Попытка сгенерировать заново."
                        )
                        # Откатываемся к логике 1-й недели, если что-то пошло не так
                        all_exercises = await exercise_requests.get_exercises_by_equipment(
                            session, user.equipment_type
                        )
                        plan = await llm_service.generate_workout_plan(
                            user=user,
                            effective_training_week=effective_week,
                            available_exercises=all_exercises
                        )
                    else:
                        plan = await llm_service.generate_workout_plan(
                            user=user,
                            effective_training_week=effective_week,
                            fixed_exercises=fixed_exercises
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
        await user_requests.increment_user_training_week(session, user.id, week_to_set=next_week)
        
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
            latest_planned_date = await get_latest_planned_date(session, user_id)

            if not latest_planned_date:
                # Первый запуск для пользователя: со следующего дня до конца недели.
                start_point = now.date() + timedelta(days=1)
                # +1 т.к. weekday() Понедельник=0, а нам нужно кол-во дней.
                days_left_in_week = 6 - start_point.weekday() + 1
                workouts_to_schedule = min(num_workouts, days_left_in_week)
                return [
                    datetime.combine(start_point + timedelta(days=i), time(12, 0))
                    for i in range(workouts_to_schedule)
                ]
            else:
                # Последующие запуски: начинаем с понедельника недели,
                # следующей за последней тренировкой.
                days_to_add = 7 - latest_planned_date.weekday()
                start_of_next_week = latest_planned_date + timedelta(days=days_to_add)
                return [
                    datetime.combine(start_of_next_week + timedelta(days=i), time(12, 0))
                    for i in range(num_workouts)
                ]

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
