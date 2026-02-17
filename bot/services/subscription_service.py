from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from bot.requests import user_requests, subscription_requests
from database.models import Subscription, User


class SubscriptionService:
    async def can_receive_workout(self, session: AsyncSession, user: User) -> bool:
        """
        Проверяет, может ли пользователь получить еще одну тренировку.
        Принимает объект User, чтобы избежать повторных запросов к БД.
        """
        if not user:
            return False

        subscription = await subscription_requests.get_subscription_by_user_id(
            session, user.id
        )
        if not subscription:
            return False

        if subscription.status == "active" and (
            subscription.expires_at is None or subscription.expires_at > datetime.now()
        ):
            return True

        if subscription.status == "trial":
            if user.workout_frequency is None or user.workout_frequency <= 0:
                return False

            if subscription.trial_workouts_used < user.workout_frequency:
                return True

        return False

    async def record_workout_sent(self, session: AsyncSession, user: User):
        """
        Фиксирует отправку тренировки. Если подписка триальная,
        увеличивает счетчик использованных тренировок.
        Принимает объект User.
        """
        subscription = await subscription_requests.get_subscription_by_user_id(
            session, user.id
        )
        if subscription and subscription.status == "trial":
            await subscription_requests.increment_trial_workouts_used(session, user.id)

    async def activate_subscription(self, session: AsyncSession, user: User) -> Subscription | None:
        """
        Активирует платную подписку на 30 дней.
        Принимает объект User.
        """
        expires_at = datetime.now() + timedelta(days=30)
        return await subscription_requests.activate_paid_subscription(
            session, user.id, expires_at
        )

    async def expire_trial_subscription(self, session: AsyncSession, user_id: int) -> Subscription | None:
        """
        Устанавливает статус подписки 'trial_expired'.
        """
        subscription = await subscription_requests.get_subscription_by_user_id(session, user_id)
        if subscription and subscription.status == "trial":
            return await subscription_requests.update_subscription_status(session, subscription.id, "trial_expired")
        return subscription


subscription_service = SubscriptionService()

