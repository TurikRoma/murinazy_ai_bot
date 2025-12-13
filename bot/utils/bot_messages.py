"""
Утилиты для безопасной отправки сообщений ботом с обработкой ошибок.
"""
import logging
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.requests import user_requests, subscription_requests


async def check_user_available(
    bot: Bot,
    session: AsyncSession,
    chat_id: int
) -> bool:
    """
    Проверяет, может ли бот отправить сообщение пользователю (не заблокирован ли бот).
    Использует send_chat_action для легкой проверки доступности.
    Если пользователь заблокировал бота, устанавливает статус подписки в trial_expired.
    
    Returns:
        True если пользователь доступен, False если заблокировал бота
    """
    try:
        # Используем send_chat_action для легкой проверки - это не отправляет сообщение пользователю
        await bot.send_chat_action(chat_id=chat_id, action="typing")
        return True
    except TelegramForbiddenError:
        logging.warning(f"User {chat_id} blocked the bot. Setting subscription status to trial_expired.")
        try:
            user = await user_requests.get_user_by_telegram_id(session, chat_id)
            if user:
                subscription = await subscription_requests.get_subscription_by_user_id(session, user.id)
                if subscription:
                    await subscription_requests.update_subscription_status(session, subscription.id, "trial_expired")
                    logging.info(f"Subscription status updated to trial_expired for user {user.id}")
        except Exception as db_error:
            logging.error(f"Failed to update subscription status for user {chat_id}: {db_error}", exc_info=True)
        return False
    except Exception as e:
        logging.error(f"Error when checking user availability for {chat_id}: {e}", exc_info=True)
        # В случае других ошибок считаем, что пользователь доступен (чтобы не блокировать генерацию из-за временных проблем)
        return True


async def safe_send_message(
    bot: Bot,
    session: AsyncSession,
    chat_id: int,
    text: str,
    **kwargs
):
    """
    Безопасно отправляет сообщение пользователю.
    Если пользователь заблокировал бота (ошибка Forbidden), устанавливает статус подписки в trial_expired.
    """
    try:
        await bot.send_message(chat_id=chat_id, text=text, **kwargs)
    except TelegramForbiddenError:
        logging.warning(f"User {chat_id} blocked the bot. Setting subscription status to trial_expired.")
        try:
            user = await user_requests.get_user_by_telegram_id(session, chat_id)
            if user:
                subscription = await subscription_requests.get_subscription_by_user_id(session, user.id)
                if subscription:
                    await subscription_requests.update_subscription_status(session, subscription.id, "trial_expired")
                    logging.info(f"Subscription status updated to trial_expired for user {user.id}")
        except Exception as db_error:
            logging.error(f"Failed to update subscription status for user {chat_id}: {db_error}", exc_info=True)
    except Exception as e:
        logging.error(f"Error when sending message to {chat_id}: {e}", exc_info=True)
