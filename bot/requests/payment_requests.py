from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Payment, User


async def create_payment(session: AsyncSession, user: User):
    """
    Сохраняет информацию об успешном платеже в базу данных.
    """
    new_payment = Payment(
        user_id=user.id,
    )
    session.add(new_payment)
    await session.commit()
    return new_payment
