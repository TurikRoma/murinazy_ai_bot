import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import async_sessionmaker
from typing import Callable, Dict, Any, Awaitable

from bot.config.settings import settings
from bot.handlers import main_router
from bot.handlers.admin import router as admin_router
from bot.middlewares.db import DbSessionMiddleware, BotObjectMiddleware, WorkoutServiceMiddleware
from database.connection import create_session_pool, create_tables
from bot.scheduler import scheduler, check_expired_subscriptions
from aiogram.dispatcher.middlewares.base import BaseMiddleware

from bot.services.workout_service import WorkoutService

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)

logger = logging.getLogger(__name__)


async def main():
    """Основная функция запуска бота"""
    logger.info("Запуск бота...")
    
    # Создание таблиц в БД
    await create_tables()
    
    # Инициализация Redis для FSM
    redis = Redis.from_url(settings.REDIS_URL)
    storage = RedisStorage(redis=redis)
    
    # Инициализация бота и диспетчера
    bot = Bot(token=settings.BOT_TOKEN, default_parse_mode="HTML")
    dp = Dispatcher(storage=storage)
    
    # Создание пула сессий БД
    session_pool = create_session_pool()
    
    # Подключение middleware
    dp.update.middleware(DbSessionMiddleware(session_pool=session_pool))
    dp.update.middleware(BotObjectMiddleware(bot_instance=bot))
    workout_service = WorkoutService(bot, session_pool)
    dp.update.middleware(WorkoutServiceMiddleware(workout_service=workout_service))
    
    # Подключение роутеров
    dp.include_router(admin_router)
    dp.include_router(main_router)
    
    # Запуск фоновых задач
    scheduler.add_job(
        check_expired_subscriptions,
        trigger="interval",
        seconds=30,
        args=[bot, session_pool],
        id="check_expired_subscriptions",
        replace_existing=True,
    )
    scheduler.start()

    # Восстановление задач планировщика
    # await restore_scheduled_jobs(bot, session_pool) # This line was removed from imports, so it's removed here.

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await redis.close()
        logger.info("Бот остановлен")


if __name__ == "__main__":
    asyncio.run(main())

