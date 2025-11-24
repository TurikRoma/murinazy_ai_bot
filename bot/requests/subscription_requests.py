from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import selectinload
from sqlalchemy import update

from database.models import Subscription, User


async def create_subscription(
    session: AsyncSession, user_id: int, status: str = "trial"
) -> Subscription:
    """Создает новую подписку для пользователя."""
    new_subscription = Subscription(user_id=user_id, status=status)
    session.add(new_subscription)
    await session.commit()
    await session.refresh(new_subscription)
    return new_subscription


async def get_subscription_by_user_id(
    session: AsyncSession, user_id: int
) -> Optional[Subscription]:
    """Получает подписку пользователя по его ID."""
    result = await session.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def update_subscription_status(
    session: AsyncSession, subscription_id: int, new_status: str
) -> Optional[Subscription]:
    """Обновляет статус подписки."""
    result = await session.execute(select(Subscription).where(Subscription.id == subscription_id))
    subscription = result.scalar_one_or_none()
    if subscription:
        subscription.status = new_status
        await session.commit()
        await session.refresh(subscription)
    return subscription


async def increment_trial_workouts_used(
    session: AsyncSession, user_id: int
) -> Optional[Subscription]:
    """Увеличивает счетчик использованных триальных тренировок на 1."""
    subscription = await get_subscription_by_user_id(session, user_id)
    if subscription and subscription.status == "trial":
        subscription.trial_workouts_used += 1
        await session.commit()
        await session.refresh(subscription)
    return subscription


async def activate_paid_subscription(
    session: AsyncSession, user_id: int, expires_at: datetime
) -> Optional[Subscription]:
    """Активирует платную подписку."""
    subscription = await get_subscription_by_user_id(session, user_id)
    if subscription:
        subscription.status = "active"
        subscription.expires_at = expires_at
        subscription.trial_workouts_used = 0  # Сбрасываем счетчик триала
        await session.commit()
        await session.refresh(subscription)
    return subscription


async def extend_subscription(
    session: AsyncSession, user_id: int, new_expires_at: datetime
) -> Subscription | None:
    """Продлевает существующую подписку."""
    stmt = (
        update(Subscription)
        .where(Subscription.user_id == user_id)
        .values(expires_at=new_expires_at, status="active")
        .returning(Subscription)
    )
    result = await session.execute(stmt)
    subscription = result.scalar_one_or_none()
    if subscription:
        await session.commit()
        await session.refresh(subscription)
    return subscription


async def get_expired_paid_subscriptions(session: AsyncSession) -> list[Subscription]:
    """Находит все активные подписки, срок действия которых уже истек."""
    result = await session.execute(
        select(Subscription)
        .options(selectinload(Subscription.user))
        .where(
            Subscription.status == "active",
            Subscription.expires_at < datetime.now()
        )
    )
    return result.scalars().all()


async def get_exhausted_trial_subscriptions(session: AsyncSession) -> list[Subscription]:
    """
    Находит все триальные подписки, у которых количество использованных
    тренировок равно или больше запланированного.
    """
    stmt = (
        select(Subscription)
        .options(selectinload(Subscription.user))
        .join(Subscription.user)
        .where(
            Subscription.status == "trial",
            Subscription.trial_workouts_used >= 1
        )
    )
    result = await session.execute(stmt)
    return result.scalars().all()
