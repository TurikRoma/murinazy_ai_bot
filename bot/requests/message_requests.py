import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from database.models import UserMessage


async def add_message(session: AsyncSession, user_id: int, message: str) -> UserMessage:
    """Сохраняет сообщение пользователя в базу данных."""
    new_message = UserMessage(user_id=user_id, message=message)
    session.add(new_message)
    await session.commit()
    await session.refresh(new_message)
    return new_message


async def count_user_messages(
    session: AsyncSession, user_id: int, since: datetime.datetime = None
) -> int:
    """
    Подсчитывает количество сообщений пользователя.
    Если указана дата `since`, то считаются сообщения после этой даты.
    """
    query = select(func.count(UserMessage.id)).where(UserMessage.user_id == user_id)
    if since:
        query = query.where(UserMessage.created_at >= since)
    
    result = await session.execute(query)
    return result.scalar_one()
