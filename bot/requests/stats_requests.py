from sqlalchemy import func, select, case
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Subscription, Payment
from bot.utils.rank_utils import RANK_THRESHOLDS


async def get_rank_distribution(session: AsyncSession):
    """
    Возвращает распределение пользователей по званиям на основе их очков.
    """
    # Сортируем пороги по убыванию для правильной логики CASE
    sorted_thresholds = sorted(RANK_THRESHOLDS.items(), key=lambda item: item[0], reverse=True)

    # Создаем условия для CASE выражения
    whens = [(User.score >= threshold, rank_name) for threshold, rank_name in sorted_thresholds]

    # Создаем CASE выражение
    rank_case = case(*whens, else_="Без звания").label("rank")

    # Формируем запрос
    stmt = (
        select(rank_case, func.count(User.id).label("user_count"))
        .group_by("rank")
        .order_by(func.count(User.id).desc())
    )

    result = await session.execute(stmt)
    return result.all()


async def get_total_user_count(session: AsyncSession) -> int:
    """
    Возвращает общее количество пользователей в системе.
    """
    stmt = select(func.count(User.id))
    result = await session.execute(stmt)
    return result.scalar_one()


async def get_total_payments_count(session: AsyncSession) -> int:
    """
    Возвращает общее количество успешных транзакций.
    """
    stmt = select(func.count(Payment.id))
    result = await session.execute(stmt)
    return result.scalar_one()


async def get_subscription_status_distribution(session: AsyncSession):
    """
    Возвращает распределение пользователей по статусу подписки.
    """
    stmt = (
        select(Subscription.status, func.count(Subscription.id))
        .group_by(Subscription.status)
        .order_by(Subscription.status)
    )
    result = await session.execute(stmt)
    return result.all()
