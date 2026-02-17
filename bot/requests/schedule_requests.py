from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload

from database.models import WorkoutSchedule, User
from bot.config.settings import DAYS_OF_WEEK_RU_FULL
import datetime


async def create_or_update_user_schedule(
    session: AsyncSession, user_id: int, schedule_data: dict[str, str] | None
):
    """
    Создает или обновляет расписание тренировок пользователя.
    Сначала удаляет старое расписание, затем создает новое (если schedule_data не None).
    Если schedule_data равен None, просто удаляет старое расписание.
    """
    # 1. Находим пользователя по telegram_id, чтобы получить его внутренний id
    user_query = await session.execute(select(User).where(User.id == user_id))
    user = user_query.scalar_one_or_none()
    if not user:
        # Можно добавить логирование или обработку ошибки
        return

    # 2. Удаляем существующее расписание для этого пользователя
    await session.execute(delete(WorkoutSchedule).where(WorkoutSchedule.user_id == user.id))
    await session.commit()

    # 3. Если schedule_data равен None, просто удаляем старое расписание и выходим
    if schedule_data is None:
        return

    # 4. Создаем новые записи расписания
    new_schedules = []
    for day_abbr, time_str in schedule_data.items():
        day_full_name = DAYS_OF_WEEK_RU_FULL.get(day_abbr)
        if not day_full_name:
            continue  # Пропускаем, если день не найден в словаре

        try:
            time_obj = datetime.datetime.strptime(time_str, "%H:%M").time()
        except ValueError:
            continue # Пропускаем некорректный формат времени

        new_schedule = WorkoutSchedule(
            user_id=user.id,
            day=day_full_name,
            notification_time=time_obj,
        )
        new_schedules.append(new_schedule)

    if new_schedules:
        session.add_all(new_schedules)
        await session.commit()


async def get_user_schedule(
    session: AsyncSession, user_id: int
) -> list[WorkoutSchedule]:
    """
    Получает все записи расписания для указанного пользователя.
    """
    stmt = select(WorkoutSchedule).where(WorkoutSchedule.user_id == user_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())
