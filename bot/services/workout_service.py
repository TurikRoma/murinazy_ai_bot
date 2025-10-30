import asyncio
import logging
from datetime import date, datetime, timedelta, time

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.requests import user_requests, exercise_requests, schedule_requests, workout_requests
from bot.requests.workout_requests import (
    save_weekly_plan,
    get_exercises_from_last_workouts,
    get_latest_planned_date,
    get_latest_future_planned_date,
)
from bot.services.llm_service import llm_service
from bot.schemas.workout import PlanSummary
from bot.utils.workout_utils import calculate_effective_training_week
from bot.services.subscription_service import subscription_service
from zoneinfo import ZoneInfo


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
                    
                    # ПРОВЕРКА: Если пользователь сменил оборудование, старый план невалиден
                    settings_are_valid = True
                    if not fixed_exercises:
                        settings_are_valid = False
                        logging.warning(f"No fixed exercises found for user {user.id} mid-cycle. Forcing regeneration.")
                    elif fixed_exercises[0].equipment_type != user.equipment_type:
                        settings_are_valid = False
                        logging.warning(f"User {user.id} changed equipment from {fixed_exercises[0].equipment_type.value} to {user.equipment_type.value}. Forcing regeneration.")

                    if settings_are_valid:
                         plan = await llm_service.generate_workout_plan(
                            user=user,
                            effective_training_week=effective_week,
                            fixed_exercises=fixed_exercises
                        )
                    else:
                        # Запускаем логику первой недели, так как настройки изменились
                        logging.info(f"Regenerating plan for user {user.id} due to settings change.")
                        # Обнуляем неделю, чтобы начать новый цикл
                        await user_requests.increment_user_training_week(session, user.id, week_to_set=1)
                        effective_week = 1 # Устанавливаем для LLM первую неделю
                        
                        all_exercises = await exercise_requests.get_exercises_by_equipment(
                            session, user.equipment_type
                        )
                        plan = await llm_service.generate_workout_plan(
                            user=user,
                            effective_training_week=effective_week,
                            available_exercises=all_exercises
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
        from bot.scheduler import scheduler, send_workout_notification
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
        Вычисляет даты тренировок со следующей логикой:
        1. Если у пользователя уже есть будущие тренировки (регенерация), новый план всегда начинается
           с недели, следующей за последней запланированной тренировкой.
        2. Если будущих тренировок нет (первая генерация), система пытается запланировать на текущую неделю.
           Если не получается, планирует на следующую.
        """
        latest_future_date = await get_latest_future_planned_date(session, user_id)
        now = datetime.now()

        # --- ЛОГИКА РЕГЕНЕРАЦИИ (когда есть будущий план) ---
        if latest_future_date:
            last_date = latest_future_date.date()
            days_to_add = 7 - last_date.weekday()
            start_search_date = last_date + timedelta(days=days_to_add)

            user_schedule = await schedule_requests.get_user_schedule(session, user_id)
            if not user_schedule:
                return [datetime.combine(start_search_date + timedelta(days=i), time(12, 0)) for i in range(num_workouts)]
            
            # Ищем слоты, начиная с высчитанной даты
            weekday_map = {"понедельник": 0, "вторник": 1, "среда": 2, "четверг": 3, "пятница": 4, "суббота": 5, "воскресенье": 6}
            slots = sorted([(weekday_map[s.day.value], s.notification_time) for s in user_schedule])
            
            found_dates = []
            for day_offset in range(14): # Ищем в пределах 2 недель
                if len(found_dates) >= num_workouts: break
                check_date = start_search_date + timedelta(days=day_offset)
                for wday, time_obj in slots:
                    if len(found_dates) >= num_workouts: break
                    if wday == check_date.weekday():
                        found_dates.append(datetime.combine(check_date, time_obj))
            
            found_dates.sort()
            return found_dates[:num_workouts]

        # --- ЛОГИКА ПЕРВОЙ ГЕНЕРАЦИИ (возвращаем старое поведение) ---
        user_schedule = await schedule_requests.get_user_schedule(session, user_id)
        if not user_schedule:
            # Пользователь без расписания: пытаемся вписать в текущую неделю с завтра
            start_point = now.date() + timedelta(days=1)
            days_left_in_week = 7 - start_point.weekday()
            
            # Если "завтра" это уже следующая неделя
            if start_point.weekday() < now.weekday():
                days_left_in_week = 0

            if days_left_in_week > 0:
                workouts_to_schedule = min(num_workouts, days_left_in_week)
                return [datetime.combine(start_point + timedelta(days=i), time(12, 0)) for i in range(workouts_to_schedule)]
            else:
                # Если не вписались, то со следующего понедельника
                days_to_add = 7 - now.date().weekday()
                start_of_next_week = now.date() + timedelta(days=days_to_add)
                return [datetime.combine(start_of_next_week + timedelta(days=i), time(12, 0)) for i in range(num_workouts)]
        else:
            # Пользователь с расписанием: ищем слоты с сегодняшнего дня
            weekday_map = {"понедельник": 0, "вторник": 1, "среда": 2, "четверг": 3, "пятница": 4, "суббота": 5, "воскресенье": 6}
            slots = sorted([(weekday_map[s.day.value], s.notification_time) for s in user_schedule])

            def find_slots_from_now(start_offset, days_to_check):
                dates = []
                for day_offset in range(start_offset, start_offset + days_to_check):
                    if len(dates) >= num_workouts: break
                    check_date = (now + timedelta(days=day_offset)).date()
                    for wday, time_obj in slots:
                        if len(dates) >= num_workouts: break
                        if wday == check_date.weekday():
                            potential_dt = datetime.combine(check_date, time_obj)
                            if potential_dt > now:
                                dates.append(potential_dt)
                return dates

            # 1. Ищем слоты на текущей неделе (начиная с сегодня)
            days_left_current_week = 7 - now.weekday()
            workout_datetimes = find_slots_from_now(0, days_left_current_week)

            # 2. Если на текущей неделе ничего не найдено, ищем на следующей
            if not workout_datetimes:
                workout_datetimes = find_slots_from_now(days_left_current_week, 7)
            
            workout_datetimes.sort()
            return workout_datetimes[:num_workouts]


async def scheduled_weekly_workout_generation(
    bot: Bot, session_pool: async_sessionmaker, workout_service: WorkoutService
):
    """
    Запускает еженедельную генерацию тренировок для всех пользователей с расписанием.
    """
    logging.info("Starting scheduled weekly workout generation for all users.")
    async with session_pool() as session:
        users = await user_requests.get_users_with_schedule(session)
        logging.info(
            f"Found {len(users)} users with schedules for weekly generation."
        )

        for user in users:
            # Открываем новую сессию для каждого пользователя для изоляции
            async with session_pool() as user_session:
                try:
                    logging.info(
                        f"Generating weekly workout for user_id: {user.id} (telegram_id: {user.telegram_id})"
                    )

                    can_receive = await subscription_service.can_receive_workout(
                        user_session, user
                    )
                    if not can_receive:
                        logging.info(
                            f"User {user.telegram_id} cannot receive workout due to subscription status. Skipping."
                        )
                        continue

                    result = await workout_service.create_and_schedule_weekly_workout(
                        user_session, user.telegram_id
                    )

                    if result:
                        _, next_workout_date = result
                        next_date_str = (
                            next_workout_date.strftime("%d.%m.%Y")
                            if next_workout_date
                            else "на следующей неделе"
                        )
                        await bot.send_message(
                            user.telegram_id,
                            f"✅ Ваша новая тренировка на неделю сгенерирована!\n\n"
                            f"Ближайшая тренировка ждет вас {next_date_str}.",
                        )
                        logging.info(
                            f"Successfully generated and notified user {user.telegram_id}."
                        )
                    else:
                        logging.warning(
                            f"Failed to generate workout for user {user.telegram_id}, result was None."
                        )

                except Exception as e:
                    logging.error(
                        f"Error generating weekly workout for user {user.telegram_id}: {e}",
                        exc_info=True,
                    )

    logging.info("Finished scheduled weekly workout generation.")


async def check_and_generate_missed_workouts(
    bot: Bot, session_pool: async_sessionmaker, workout_service: WorkoutService
):
    """
    Проверяет пользователей, которые могли пропустить еженедельную генерацию, и запускает ее.
    """
    logging.info("Checking for users with missed weekly workouts...")
    async with session_pool() as session:
        users = await user_requests.get_users_with_schedule(session)
        if not users:
            logging.info(
                "No users with schedules found. Skipping missed workout check."
            )
            return

        now = datetime.now()
        last_sunday = now - timedelta(days=(now.weekday() + 1) % 7)
        last_sunday_22_00_utc = datetime(
            last_sunday.year,
            last_sunday.month,
            last_sunday.day,
            22,
            0,
            0,
            tzinfo=ZoneInfo("Europe/Moscow"),
        ).astimezone(tz=None)

        logging.info(f"Checking against last generation time: {last_sunday_22_00_utc}")

        for user in users:
            async with session_pool() as user_session:
                try:
                    last_workout_date = await workout_requests.get_last_workout_date(
                        user_session, user.id
                    )

                    if (
                        last_workout_date is None
                        or last_workout_date.replace(tzinfo=None) < last_sunday_22_00_utc.replace(tzinfo=None)
                    ):
                        logging.info(
                            f"User {user.telegram_id} missed workout generation. Last one was at {last_workout_date}. Generating now."
                        )

                        can_receive = await subscription_service.can_receive_workout(
                            user_session, user
                        )
                        if not can_receive:
                            logging.info(
                                f"User {user.telegram_id} cannot receive workout due to subscription status. Skipping."
                            )
                            continue

                        result = (
                            await workout_service.create_and_schedule_weekly_workout(
                                user_session, user.telegram_id
                            )
                        )
                        if result:
                            await bot.send_message(
                                user.telegram_id,
                                "ℹ️ Мы заметили, что ваша тренировка на этой неделе не была создана. "
                                "Мы все исправили, новый план уже готов!",
                            )
                            logging.info(
                                f"Successfully generated missed workout for user {user.telegram_id}."
                            )
                        else:
                            logging.warning(
                                f"Failed to generate missed workout for user {user.telegram_id}, result was None."
                            )

                except Exception as e:
                    logging.error(
                        f"Error in missed workout check for user {user.telegram_id}: {e}",
                        exc_info=True,
                    )

    logging.info("Finished checking for missed workouts.")
