from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import LlmMessage


class LlmRequests:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_message(self, user_id: int, message: str) -> LlmMessage:
        llm_message = LlmMessage(user_id=user_id, message=message)
        self.session.add(llm_message)
        await self.session.commit()
        return llm_message

    async def count_user_messages(self, user_id: int) -> int:
        stmt = select(func.count(LlmMessage.id)).where(LlmMessage.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()
