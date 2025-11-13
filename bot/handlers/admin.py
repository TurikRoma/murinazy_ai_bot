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
from bot.requests.stats_requests import (
    get_rank_distribution,
    get_subscription_status_distribution,
    get_total_user_count,
    get_total_payments_count,
)


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

    # Получаем аргументы команды
    args = message.text.split()
    force_generate = len(args) > 1 and args[1].lower() == "true"

    # Проверяем подписку админа перед генерацией
    admin_user = await get_user_by_telegram_id(session, message.from_user.id)
    if not admin_user or not await subscription_service.can_receive_workout(session, admin_user):
        logging.info(f"Admin {message.from_user.id} has no active subscription. Skipping /generate.")
        return

    # Проверяем, есть ли уже запланированные тренировки (если не принудительно)
    if not force_generate:
        next_workout = await get_next_workout_for_user(session, admin_user.id)
        if next_workout:
            await message.answer(
                "У вас уже есть запланированные тренировки на этой неделе. "
                f"Следующая тренировка: {next_workout.planned_date.strftime('%d.%m.%Y')}.\n\n"
                "Чтобы сгенерировать план на следующую неделю, используйте `/generate true`."
            )
            return

    loading_message = await message.answer(
        "⏳ Начинаю генерацию недельного плана для вашего аккаунта..."
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


@router.message(Command("stats"), is_admin)
async def get_stats_command(message: Message, session: AsyncSession):
    """
    Отображает статистику по званиям и статусам подписок пользователей.
    """
    try:
        # Общее количество пользователей
        total_users = await get_total_user_count(session)
        
        # Статистика по званиям
        rank_stats = await get_rank_distribution(session)
        stats_text = f"<b>📊 Общая статистика</b>\n"
        stats_text += f"<b>Всего пользователей:</b> {total_users}\n\n"
        
        stats_text += "<b>🏆 Статистика по званиям:</b>\n"
        if rank_stats:
            total_ranked_users = sum(count for _, count in rank_stats)
            for rank_name, count in rank_stats:
                stats_text += f"▪️ {rank_name}: {count}\n"
        else:
            stats_text += "Нет данных.\n"

        # Статистика по подпискам
        subscription_stats = await get_subscription_status_distribution(session)
        total_payments = await get_total_payments_count(session)
        stats_text += "\n<b>📊 Подписки:</b>\n"
        stats_text += f"<b>Всего покупок за все время:</b> {total_payments}\n На текущий момент:\n\n"
        if subscription_stats:
            total_subscriptions = 0
            paid_users = 0
            free_users = 0
            
            status_map = {
                'active': '✅ Активные (Люди с подпиской)',
                'trial': '⏳ Пробные',
                'expired': '❌ Истекли (Люди у которых была подписка, но она истекла)',
                'trial_expired': '🚫 Пробные истекли(Неактивные пользователи)'
            }

            for status, count in subscription_stats:
                status_name = status_map.get(status.value, status.value.capitalize())
                stats_text += f"▪️ {status_name}: {count}\n"
                total_subscriptions += count
                if status.value == 'active':
                    paid_users = count
                elif status.value == 'trial':
                    free_users = count
            
            stats_text += f"\n<b>Итог:</b>\n"
            stats_text += f"<b>💳 Платные:</b> {paid_users}\n"
            stats_text += f"<b>🆓 Бесплатные (триал):</b> {free_users}\n"
        else:
            stats_text += "Нет данных."
        
        await message.answer(stats_text, parse_mode="HTML")

    except Exception as e:
        logging.error(f"Error in /stats command: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка при получении статистики.")
