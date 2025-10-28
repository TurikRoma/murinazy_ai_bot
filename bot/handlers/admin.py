from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from bot.config.settings import settings
from bot.services.workout_service import WorkoutService


router = Router()


@router.message(Command("generate"))
async def generate_workout_command(
    message: Message, session: AsyncSession, workout_service: WorkoutService
):
    """
    Ручная генерация недельного плана тренировок для администратора.
    Имитирует еженедельный скрипт, принудительно создавая новый план.
    """
    if message.from_user.id != settings.ADMIN_ID:
        logging.warning(
            f"Non-admin user {message.from_user.id} tried to use /generate"
        )
        return

    loading_message = await message.answer(
        "⏳ Начинаю принудительную генерацию недельного плана для вашего аккаунта..."
    )

    try:
        result = await workout_service.create_and_schedule_weekly_workout(
            session, message.from_user.id
        )

        if result:
            summary, next_workout_date = result
            if next_workout_date:
                date_str = next_workout_date.strftime('%d.%m.%Y в %H:%M')
            else:
                date_str = "не определена"

            await loading_message.edit_text(
                f"✅ Успешно сгенерирован новый план!\n\n"
                f"<b>Сплит:</b> {summary.split_type}\n"
                f"<b>Тип периодизации:</b> {summary.periodization_type}\n"
                f"<b>Цель недели:</b> {summary.primary_goal}\n\n"
                f"🗓️ Ближайшая тренировка запланирована на {date_str}.",
                parse_mode="HTML",
            )
        else:
            await loading_message.edit_text(
                "❌ Не удалось сгенерировать план. Возможно, на этой неделе уже нет свободных дней. Попробуйте в понедельник."
            )

    except Exception as e:
        logging.error(f"Error during manual workout generation: {e}", exc_info=True)
        await loading_message.edit_text(
            "❌ Произошла критическая ошибка при генерации тренировки. "
            "Свяжитесь с разработчиком."
        )
