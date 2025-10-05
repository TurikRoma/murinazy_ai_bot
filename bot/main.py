import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from config.settings import settings
from bot.handlers import registration, profile, workout
from bot.middlewares.db import DbSessionMiddleware
from database.connection import create_session_pool

logger = logging.getLogger(__name__)


async def main():
    """Основная функция запуска бота"""
    logger.info("Запуск бота...")
    
    # Инициализация Redis для FSM
    redis = Redis.from_url(settings.REDIS_URL)
    storage = RedisStorage(redis=redis)
    
    # Инициализация бота и диспетчера
    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher(storage=storage)
    
    # Создание пула сессий БД
    session_pool = create_session_pool()
    
    # Подключение middleware
    dp.update.middleware(DbSessionMiddleware(session_pool=session_pool))
    
    # Регистрация handlers
    dp.include_router(registration.router)
    dp.include_router(profile.router)
    dp.include_router(workout.router)
    
    # Запуск polling
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await redis.close()
        logger.info("Бот остановлен")


if __name__ == "__main__":
    asyncio.run(main())

