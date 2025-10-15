from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.requests.user_requests import get_user_by_telegram_id
from bot.services.workout_service import workout_service, WorkoutCooldownError
from database.models import User

router = Router()


async def send_workout_plan(message: Message, session: AsyncSession, user: User):
    """
    Универсальная функция для генерации и отправки тренировки.
    """
    # Показываем пользователю, что бот работает
    loading_message = await message.answer("🏋️‍♂️ Генерирую вашу персональную тренировку...")

    try:
        new_workout = await workout_service.create_new_workout_plan(session, user)
        response_text = workout_service.format_workout_message(new_workout)
        await loading_message.edit_text(response_text, parse_mode="Markdown")

    except WorkoutCooldownError as e:
        await loading_message.edit_text(e.message)
    except Exception as e:
        await loading_message.edit_text(
            "❌ Произошла ошибка при генерации тренировки. "
            "Попробуйте еще раз или свяжитесь с поддержкой."
        )
        # TODO: Добавить логирование ошибки
        print(f"Error generating workout: {e}") # Временное логирование


@router.message(Command("workout"))
async def get_workout_handler(message: Message, session: AsyncSession):
    """
    Обработчик команды /workout.
    """
    user = await get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        await message.answer(
            "Пожалуйста, сначала пройдите регистрацию с помощью команды /start."
        )
        return

    await send_workout_plan(message, session, user)

