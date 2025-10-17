from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.requests.user_requests import get_user_by_telegram_id
from bot.requests.workout_requests import get_workout_with_exercises, update_workout_status
from bot.services.workout_service import WorkoutService
from database.models import User, Workout, WorkoutStatusEnum

router = Router()


def format_workout_message(workout: Workout) -> str:
    """Форматирует красивый текстовый ответ с программой тренировок."""
    exercises_text = "\n".join(
        [
            f"  - {we.exercise.name}: {we.sets} подхода по {we.reps} повторений"
            for we in sorted(workout.workout_exercises, key=lambda x: x.order)
        ]
    )
    message = (
        f"🔥 <b>Тренировка на {workout.planned_date.strftime('%d.%m.%Y')}</b>\n\n"
        f"Вот ваш план:\n{exercises_text}\n\n"
        f"Не забудьте сделать разминку перед началом и отметку о завершении после."
    )
    return message


@router.callback_query(F.data.startswith("get_workout_now_"))
async def get_workout_now_handler(query: CallbackQuery, session: AsyncSession):
    """
    Обработчик кнопки "Получить тренировку сейчас".
    """
    workout_id = int(query.data.split("_")[-1])
    workout = await get_workout_with_exercises(session, workout_id)

    if workout:
        message_text = format_workout_message(workout)
        # TODO: Добавить кнопку "Завершить тренировку"
        await query.message.answer(message_text, parse_mode="HTML")
    else:
        await query.message.answer("Не удалось найти эту тренировку. Возможно, она была удалена.")
    
    await query.answer()


@router.callback_query(F.data.startswith("workout_completed_"))
async def workout_completed_handler(query: CallbackQuery, session: AsyncSession):
    """Обрабатывает нажатие кнопки 'Завершил'."""
    workout_id = int(query.data.split("_")[-1])
    await update_workout_status(session, workout_id, WorkoutStatusEnum.completed)
    await query.message.edit_text(
        "✅ Отлично, тренировка отмечена как **завершенная**!",
        parse_mode="Markdown"
    )
    await query.answer()


@router.callback_query(F.data.startswith("workout_skipped_"))
async def workout_skipped_handler(query: CallbackQuery, session: AsyncSession):
    """Обрабатывает нажатие кнопки 'Пропустил'."""
    workout_id = int(query.data.split("_")[-1])
    await update_workout_status(session, workout_id, WorkoutStatusEnum.skipped)
    await query.message.edit_text(
        "😔 Понятно. Тренировка отмечена как **пропущенная**.",
        parse_mode="Markdown"
    )
    await query.answer()


@router.message(Command("workout"))
async def get_workout_handler(
    message: Message, session: AsyncSession, workout_service: WorkoutService
):
    """
    Обработчик команды /workout для генерации новой разовой тренировки.
    """
    user = await get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        await message.answer(
            "Пожалуйста, сначала пройдите регистрацию с помощью команды /start."
        )
        return

    loading_message = await message.answer("🏋️‍♂️ Генерирую вашу персональную тренировку...")

    try:
        # Эта логика теперь внутри WorkoutService, но для разовой генерации можно оставить так
        # или вынести в отдельный метод сервиса. Пока оставляем для обратной совместимости.
        new_workout = await workout_service.create_new_workout_plan(session, user)
        response_text = format_workout_message(new_workout)
        await loading_message.edit_text(response_text, parse_mode="HTML")

    except Exception as e:
        await loading_message.edit_text(
            "❌ Произошла ошибка при генерации тренировки. "
            "Попробуйте еще раз или свяжитесь с поддержкой."
        )
        # TODO: Добавить логирование ошибки
        print(f"Error generating workout: {e}")

