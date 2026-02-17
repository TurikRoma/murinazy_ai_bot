from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime

from database.models import User, WorkoutSchedule, Subscription, SubscriptionStatusEnum
from bot.schemas.user import UserRegistrationSchema
from bot.utils.rank_utils import get_rank_by_score


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


async def increment_user_training_week(
    session: AsyncSession, user_id: int, week_to_set: int | None = None
) -> User | None:
    """
    Устанавливает номер недели тренировок пользователя.
    Если week_to_set не передано, увеличивает на 1.
    """
    user = await session.get(User, user_id)
    if user:
        if week_to_set is not None:
            user.current_training_week = week_to_set
        else:
            if user.current_training_week is None:
                user.current_training_week = 1
            else:
                user.current_training_week += 1
        await session.commit()
        await session.refresh(user)
    return user


async def add_score_to_user(
    session: AsyncSession, user_id: int, points: int = 1
) -> tuple[User | None, str, str]:
    """Добавляет очки пользователю и возвращает старое и новое звание."""
    user = await session.get(User, user_id)
    if user:
        old_score = user.score or 0
        old_rank = get_rank_by_score(old_score)

        user.score = old_score + points
        await session.commit()
        await session.refresh(user)

        new_rank = get_rank_by_score(user.score)
        return user, old_rank, new_rank

    return None, "Без звания", "Без звания"


async def get_users_with_schedule(session: AsyncSession) -> list[User]:
    """Получает всех пользователей, у которых есть хотя бы одна запись в расписании."""
    stmt = select(User).join(User.workout_schedules).distinct()
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_users_for_workout_generation(session: AsyncSession) -> list[User]:
    """
    Получает всех пользователей, которым нужны тренировки:
    - Пользователи с расписанием (workout_schedules)
    - ИЛИ пользователи с активной подпиской (active или trial)
    """
    # Получаем пользователей с расписанием
    users_with_schedule = await get_users_with_schedule(session)
    
    # Получаем всех пользователей с подпиской и фильтруем в Python
    # Это позволяет избежать проблем с типами Enum в SQL запросах
    now = datetime.now()
    stmt = (
        select(User)
        .join(User.subscription)
        .options(selectinload(User.subscription))
    )
    result = await session.execute(stmt)
    all_users_with_subscription = list(result.scalars().all())
    
    # Фильтруем пользователей с активной подпиской
    users_with_active_subscription = []
    for user in all_users_with_subscription:
        if not user.subscription:
            continue
        
        subscription = user.subscription
        status_str = subscription.status.value if isinstance(subscription.status, SubscriptionStatusEnum) else str(subscription.status)
        
        # Активная подписка (не истекла)
        if status_str == "active" and (
            subscription.expires_at is None or subscription.expires_at > now
        ):
            users_with_active_subscription.append(user)
        # Триальная подписка (есть доступные тренировки)
        elif status_str == "trial" and (
            user.workout_frequency is not None
            and user.workout_frequency > 0
            and subscription.trial_workouts_used < user.workout_frequency
        ):
            users_with_active_subscription.append(user)
    
    # Объединяем списки, убирая дубликаты
    all_users = {user.id: user for user in users_with_schedule}
    for user in users_with_active_subscription:
        if user.id not in all_users:
            all_users[user.id] = user
    
    return list(all_users.values())