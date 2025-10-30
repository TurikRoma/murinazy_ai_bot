from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from bot.config.settings import settings
from bot.services.workout_service import WorkoutService
from bot.requests.user_requests import get_user_by_telegram_id
from bot.requests.workout_requests import get_next_workout_for_user, get_workout_with_exercises
from bot.handlers.workout import format_workout_message, get_start_workout_keyboard
from bot.services.subscription_service import subscription_service
from datetime import datetime, timedelta
from database.models import WorkoutStatusEnum


router = Router()

def is_admin(message: Message) -> bool:
    return message.from_user.id == settings.ADMIN_ID

@router.message(Command("generate"), is_admin)
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

    # Проверяем подписку админа перед генерацией
    admin_user = await get_user_by_telegram_id(session, message.from_user.id)
    if not admin_user or not await subscription_service.can_receive_workout(session, admin_user):
        logging.info(f"Admin {message.from_user.id} has no active subscription. Skipping /generate.")
        return

    # Проверяем, есть ли уже запланированные тренировки
    next_workout = await get_next_workout_for_user(session, admin_user.id)
    if next_workout:
        await message.answer(
            "У вас уже есть запланированные тренировки на этой неделе. "
            f"Следующая тренировка: {next_workout.planned_date.strftime('%d.%m.%Y')}."
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


@router.message(Command("next"), is_admin)
async def next_workout_command(message: Message, session: AsyncSession):
    """
    Имитирует отправку следующей запланированной тренировки для администратора.
    Выполняет все проверки подписки и отмечает тренировку как отправленную.
    """
    admin_user = await get_user_by_telegram_id(session, message.from_user.id)
    if not admin_user:
        await message.answer("Ваш профиль не найден. Пожалуйста, пройдитесь по /start")
        return

    # 1. Проверяем, может ли админ получить тренировку
    can_get_workout = await subscription_service.can_receive_workout(session, admin_user)
    if not can_get_workout:
        await message.answer("Вам не положена тренировка. Лимит исчерпан или подписка неактивна.")
        return

    # 2. Находим следующую тренировку
    next_workout_info = await get_next_workout_for_user(session, admin_user.id)
    if not next_workout_info:
        await message.answer("Нет запланированных тренировок для отправки.")
        return

    # 3. Получаем ПОЛНУЮ тренировку с упражнениями, чтобы избежать lazy load
    full_workout = await get_workout_with_exercises(session, next_workout_info.id)
    if not full_workout:
        await message.answer(f"Не удалось загрузить детали тренировки #{next_workout_info.id}.")
        return

    # 4. Отправляем карточку тренировки
    message_text = format_workout_message(full_workout)
    await message.answer(
        message_text,
        reply_markup=get_start_workout_keyboard(full_workout.id),
        parse_mode="HTML",
    )

    # 5. Фиксируем отправку (важно для триала)
    await subscription_service.record_workout_sent(session, admin_user)
    await message.answer(f"✅ Тренировка #{full_workout.id} успешно отправлена и засчитана.")


@router.message(Command("refund"), is_admin)
async def refund_command(message: Message):
    """
    Возвращает Telegram Stars по ID транзакции.
    """
    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            "Пожалуйста, укажите ID транзакции для возврата.\n"
            "Пример: `/refund 123456789_ABCDEFG`"
        )
        return

    telegram_payment_charge_id = args[1]
    try:
        success = await message.bot.refund_star_payment(
            user_id=message.from_user.id,
            telegram_payment_charge_id=telegram_payment_charge_id
        )
        if success:
            await message.answer(f"✅ Успешный возврат для транзакции `{telegram_payment_charge_id}`")
        else:
            await message.answer(f"❌ Не удалось выполнить возврат для транзакции `{telegram_payment_charge_id}`")
    except Exception as e:
        logging.error(f"Refund failed for transaction {telegram_payment_charge_id}: {e}")
        await message.answer(f"❌ Произошла ошибка при возврате: {e}")
