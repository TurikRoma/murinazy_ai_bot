import asyncio
import logging
from datetime import date, datetime, timedelta, time

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.requests import user_requests, exercise_requests, schedule_requests
from bot.requests.workout_requests import save_weekly_plan
from bot.scheduler import scheduler, send_workout_notification
from bot.services.llm_service import llm_service


class WorkoutService:
    def __init__(self, bot: Bot, session_pool: async_sessionmaker):
        self.bot = bot
        self.session_pool = session_pool

    async def create_and_schedule_weekly_workout(
        self, session: AsyncSession, telegram_id: int
    ) -> datetime | None:
        """
        Главный метод: генерирует, сохраняет и планирует недельный план тренировок.
        Возвращает datetime следующей тренировки или None.
        """
        user = await user_requests.get_user_by_telegram_id(session, telegram_id)
        if not user:
            logging.error(f"User with telegram_id {telegram_id} not found.")
            return None

        # 1. Генерация плана через LLM с retry-логикой
        plan = None
        for attempt in range(2):
            try:
                all_exercises = await exercise_requests.get_exercises_by_equipment(
                    session, user.equipment_type
                )
                plan = await llm_service.generate_workout_plan(user, all_exercises)
                print(plan)
                break  # Успешная генерация, выходим из цикла
            except Exception as e:
                logging.error(f"LLM workout generation failed on attempt {attempt + 1}: {e}")
                if attempt == 0:
                    await asyncio.sleep(1)  # Пауза перед повторной попыткой

        if not plan:
            # Если не удалось сгенерировать, возвращаем None, обработчик отправит сообщение
            return None

        # 2. Определение дат тренировок
        workout_dates = await self._calculate_workout_datetimes(session, user.id, len(plan.sessions))
        if not workout_dates:
            return None # Если не удалось рассчитать даты, выходим

        # 3. Сохранение плана и дат в БД
        workouts = await save_weekly_plan(session, user.id, plan, workout_dates)
        if not workouts:
            return None # Если не удалось сохранить, выходим

        # 4. Планирование уведомлений
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

        # 5. Возвращаем дату ближайшей тренировки
        return workouts[0].planned_date if workouts else None

    async def _calculate_workout_datetimes(
        self, session: AsyncSession, user_id: int, num_workouts: int
    ) -> list[datetime]:
        """
        Вычисляет точные дату и время для N тренировок на основе расписания пользователя,
        учитывая текущее время, чтобы не планировать на прошлое.
        """
        user_schedule = await schedule_requests.get_user_schedule(session, user_id)
        now = datetime.now()

        if not user_schedule:
            # Если расписания нет, планируем с интервалом в 24 часа от сейчас
            return [now + timedelta(days=i) for i in range(num_workouts)]

        weekday_map = {
            "понедельник": 0, "вторник": 1, "среда": 2, "четверг": 3,
            "пятница": 4, "суббота": 5, "воскресенье": 6
        }
        slots = sorted(
            [(weekday_map[s.day.value], s.notification_time) for s in user_schedule]
        )

        workout_datetimes = []
        search_from = now

        while len(workout_datetimes) < num_workouts:
            found_slot = None
            # Ищем ближайший слот в пределах следующих 14 дней для надежности
            for day_offset in range(14):
                check_date = (search_from + timedelta(days=day_offset)).date()
                for wday, time_obj in slots:
                    if wday == check_date.weekday():
                        potential_dt = datetime.combine(check_date, time_obj)
                        if potential_dt > search_from:
                            found_slot = potential_dt
                            break
                if found_slot:
                    break
            
            if found_slot:
                workout_datetimes.append(found_slot)
                search_from = found_slot  # Следующий поиск начинаем от найденного времени
            else:
                # Если в ближайшие 2 недели ничего нет, прерываемся, чтобы избежать бесконечного цикла
                break
                
        return workout_datetimes
