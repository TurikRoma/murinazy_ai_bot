import logging

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import async_sessionmaker
from datetime import datetime
from apscheduler.triggers.cron import CronTrigger

from bot.keyboards.workout import get_start_workout_keyboard
from bot.requests.workout_requests import (
    get_workout_with_exercises,
    get_future_planned_workouts,
    update_workout_status,
)
from database.models import WorkoutStatusEnum
from bot.requests import subscription_requests
from bot.keyboards.workout import get_notification_keyboard
from bot.keyboards.payment import get_payment_keyboard
from bot.services.workout_service import (
    WorkoutService,
    scheduled_weekly_workout_generation,
)

scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
logger = logging.getLogger(__name__)


async def send_workout_notification(
    bot: Bot, user_id: int, workout_id: int, session_pool: async_sessionmaker
):
    """
    Отправляет уведомление с полной тренировкой.
    """
    async with session_pool() as session:
        workout = await get_workout_with_exercises(session, workout_id)
        if not workout:
            logger.warning(
                f"Тренировка с ID {workout_id} не найдена для отправки уведомления."
            )
            return

        # TODO: Сделать красивое форматирование
        exercises_text = "\n".join(
            [
                f"{idx + 1}: {we.exercise.name} ({we.sets} сета по {we.reps} повт.)"
                for idx, we in enumerate(workout.workout_exercises)
            ]
        )
        message = (
            f"🔥 <b>Ваша тренировка на сегодня готова!</b>\n\n"
            f"<b>Разминка:</b> {workout.warm_up}\n\n"
            f"Вот ваш план:\n{exercises_text}\n\n"
            f"<b>Заминка:</b> {workout.cool_down}\n\n"
            f"Не забудьте сделать разминку перед началом."
        )

        await bot.send_message(
            user_id,
            message,
            reply_markup=get_start_workout_keyboard(workout_id),
            parse_mode="HTML"
        )
        logger.info(
            f"Уведомление о тренировке #{workout_id} успешно отправлено пользователю {user_id}"
        )

        # Обновляем статус тренировки на "отправлено"
        await update_workout_status(session, workout_id, WorkoutStatusEnum.sent)
        logger.info(
            f"Статус тренировки #{workout_id} обновлен на '{WorkoutStatusEnum.sent.value}'"
        )


async def restore_scheduled_jobs(bot: Bot, session_pool: async_sessionmaker):
    """
    Восстанавливает запланированные уведомления о тренировках после перезапуска.
    """
    async with session_pool() as session:
        workouts = await get_future_planned_workouts(session)
        logger.info(f"Найдено {len(workouts)} тренировок для восстановления.")
        for workout in workouts:
            scheduler.add_job(
                send_workout_notification,
                "date",
                run_date=workout.planned_date,
                args=[bot, workout.user.telegram_id, workout.id, session_pool],
                id=f"workout_notification_{workout.id}",
                replace_existing=True,
            )
            logger.info(
                f"Запланировано уведомление для тренировки #{workout.id} "
                f"пользователя {workout.user.telegram_id} на {workout.planned_date}"
            )


async def check_expired_subscriptions(bot: Bot, session_pool: async_sessionmaker):
    """
    Проверяет и обрабатывает истекшие платные и триальные подписки.
    """
    logging.info("Running scheduled job: check_expired_subscriptions")
    async with session_pool() as session:
        # 1. Обработка истекших платных подписок
        expired_paid = await subscription_requests.get_expired_paid_subscriptions(session)
        for sub in expired_paid:
            logging.info(f"Subscription for user {sub.user_id} has expired. Updating status to 'expired'.")
            await subscription_requests.update_subscription_status(session, sub.id, "expired")
            try:
                await bot.send_message(
                    chat_id=sub.user.telegram_id,
                    text="ℹ️ Ваша подписка истекла. Чтобы продолжать получать тренировки, пожалуйста, оформите новую.",
                    reply_markup=get_payment_keyboard()
                )
            except Exception as e:
                logging.error(f"Failed to send expiration notification to user {sub.user_id}: {e}")

        # 2. Обработка триальных подписок, у которых закончились тренировки
        exhausted_trials = await subscription_requests.get_exhausted_trial_subscriptions(session)
        for sub in exhausted_trials:
            logging.info(f"Trial for user {sub.user_id} has expired. Updating status to 'trial_expired'.")
            # Меняем статус, чтобы уведомление не отправлялось повторно
            await subscription_requests.update_subscription_status(session, sub.id, "trial_expired")
            try:
                await bot.send_message(
                    chat_id=sub.user.telegram_id,
                    text="👋 Ваш пробный период завершен. Чтобы получать следующие   тренировки, оформите подписку.",
                    reply_markup=get_payment_keyboard()
                )
            except Exception as e:
                logging.error(f"Failed to send trial expiration notification to user {sub.user_id}: {e}")


def setup_scheduler(bot: Bot, session_pool: async_sessionmaker, workout_service: WorkoutService):
    """Настраивает и запускает все фоновые задачи."""
    # Задача 1: Проверка истекших подписок (каждые 30 секунд)
    scheduler.add_job(
        check_expired_subscriptions,
        trigger="interval",
        hours=4,
        args=[bot, session_pool],
        id="check_expired_subscriptions",
        replace_existing=True,
    )

    # Задача 2: Еженедельная генерация тренировок (каждое ВС в 22:00)
    scheduler.add_job(
        scheduled_weekly_workout_generation,
        trigger=CronTrigger(day_of_week="sun", hour=22, minute=0),
        args=[bot, session_pool, workout_service],
        id="weekly_workout_generation",
        replace_existing=True,
        misfire_grace_time=3600,  # 1 час
    )

    scheduler.start()
    logger.info("Scheduler started with all jobs.")
