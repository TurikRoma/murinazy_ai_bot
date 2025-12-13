"""
Утилиты для безопасной отправки сообщений ботом с обработкой ошибок.
"""
import logging
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession

from bot.requests import user_requests, subscription_requests


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
    except TelegramBadRequest as e:
        if "forbidden" in str(e).lower():
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
        else:
            logging.error(f"TelegramBadRequest when sending message to {chat_id}: {e}")
    except Exception as e:
        logging.error(f"Error when sending message to {chat_id}: {e}", exc_info=True)
