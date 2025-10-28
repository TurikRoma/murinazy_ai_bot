from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models import User
from bot.schemas.user import UserRegistrationSchema


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    """Получает пользователя по его Telegram ID."""
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalars().first()


async def create_or_update_user(
    session: AsyncSession,
    user_data: UserRegistrationSchema,
    telegram_id: int
) -> User:
    """Создает или обновляет пользователя в базе данных."""
    user = await get_user_by_telegram_id(session, telegram_id)
    
    user_data_dict = user_data.model_dump(exclude_none=True)

    if user:
        # Обновляем существующего пользователя
        for key, value in user_data_dict.items():
            setattr(user, key, value)
    else:
        # Создаем нового пользователя
        user = User(telegram_id=telegram_id, **user_data_dict)
        session.add(user)

    await session.commit()
    await session.refresh(user)
    return user


async def increment_user_training_week(session: AsyncSession, user_id: int) -> User | None:
    """Увеличивает счетчик недель тренировок пользователя на 1."""
    user = await session.get(User, user_id)
    if user:
        if user.current_training_week is None:
            user.current_training_week = 1
        else:
            user.current_training_week += 1
        await session.commit()
        await session.refresh(user)
    return user


async def add_score_to_user(session: AsyncSession, user_id: int, points: int = 1) -> User | None:
    """Добавляет очки пользователю за выполнение тренировки."""
    user = await session.get(User, user_id)
    if user:
        user.score = (user.score or 0) + points
        await session.commit()
        await session.refresh(user)
    return user