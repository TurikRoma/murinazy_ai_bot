from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.handlers.start import start_registration_process
from bot.keyboards.registration import get_main_menu_keyboard, get_profile_inline_keyboard
from bot.requests.user_requests import get_user_by_telegram_id
from bot.requests.schedule_requests import get_user_schedule
from bot.utils.rank_utils import get_rank_by_score, get_next_rank_threshold
from bot.utils.profile_helpers import get_training_week_description
from bot.keyboards.payment import get_payment_keyboard
from bot.keyboards.subscription import get_extend_subscription_keyboard
from bot.requests import subscription_requests
from datetime import datetime, timedelta
import logging
from aiogram.types import LabeledPrice
from database.models import User, Subscription, WorkoutSchedule
from typing import List

router = Router()

# Словарь для красивого отображения данных пользователю
HUMAN_READABLE_NAMES = {
    "gender": "Пол",
    "age": "Возраст",
    "height": "Рост",
    "current_weight": "Текущий вес",
    "fitness_level": "Уровень подготовки",
    "goal": "Цель",
    "target_weight": "Целевой вес",
    "workout_frequency": "Частота тренировок",
    "equipment_type": "Тип оборудования",
    "workout_schedule": "Расписание",
    # --- значения ---
    "male": "Мужской",
    "female": "Женский",
    "beginner": "Начинающий",
    "intermediate": "Опыт 1-3 года",
    "advanced": "Опыт >3 лет",
    "mass_gain": "Набор массы",
    "weight_loss": "Похудение",
    "maintenance": "Поддержание формы",
    "gym": "Тренажерный зал",
    "bodyweight": "Свой вес",
}

# Словарь для перевода коротких дней недели в полные
DAYS_SHORT_TO_FULL = {
    "Пн": "понедельник",
    "Вт": "вторник",
    "Ср": "среда",
    "Чт": "четверг",
    "Пт": "пятница",
    "Сб": "суббота",
    "Вс": "воскресенье",
}

# Обратный словарь
DAYS_FULL_TO_SHORT = {v: k for k, v in DAYS_SHORT_TO_FULL.items()}


def format_full_profile_text(
    user: User, schedule_list: List[WorkoutSchedule], subscription: Subscription | None
) -> str:
    """
    Форматирует данные пользователя, расписание и подписку для отображения в профиле.
    """
    profile_text = "<b>👤 Ваш профиль</b>\n\n"

    # 1. Очки и звание
    user_score = user.score or 0
    user_rank = get_rank_by_score(user_score)
    next_rank_info = get_next_rank_threshold(user_score)

    profile_text += f"🏆 <b>Звание:</b> {user_rank}\n"
    profile_text += f"⭐ <b>Очки:</b> {user_score}"

    if next_rank_info:
        next_threshold, next_rank = next_rank_info
        points_to_next = next_threshold - user_score
        profile_text += f" (до <b>{next_rank}</b> осталось {points_to_next} очков)"

    profile_text += "\n" + "─" * 20 + "\n"

    # 2. Текущий цикл тренировок
    training_week_info = get_training_week_description(user)
    if training_week_info:
        profile_text += f"\n<b>📈 Текущий цикл:</b> {training_week_info}\n"
    
    profile_text += "\n" + "─" * 20 + "\n\n"

    # 3. Основные данные
    fields = [
        ("gender", user.gender),
        ("age", user.age),
        ("height", user.height),
        ("current_weight", user.current_weight),
        ("fitness_level", user.fitness_level),
        ("goal", user.goal),
        ("target_weight", user.target_weight),
        ("workout_frequency", user.workout_frequency),
        ("equipment_type", user.equipment_type),
    ]

    for field_name, value in fields:
        if value is None:
            continue

        display_name = HUMAN_READABLE_NAMES.get(field_name, field_name)

        if hasattr(value, "value"):  # Enum
            display_value = HUMAN_READABLE_NAMES.get(value.value, str(value.value))
        else:
            display_value = str(value)
            if field_name == "workout_frequency":
                display_value = f"{value} раз(а) в неделю"
            elif field_name in ["current_weight", "target_weight"]:
                display_value = f"{value} кг"
            elif field_name == "height":
                display_value = f"{value} см"

        profile_text += f"<b>{display_name}</b>: {display_value}\n"

    # 3. Расписание
    if schedule_list:
        schedule_items = []
        for schedule in schedule_list:
            day_short = DAYS_FULL_TO_SHORT.get(
                schedule.day.value, schedule.day.value
            )
            time_str = schedule.notification_time.strftime("%H:%M")
            schedule_items.append(f"{day_short} в {time_str}")
        schedule_str = ", ".join(schedule_items)
        profile_text += f"<b>Расписание</b>: {schedule_str}\n"
    else:
        profile_text += "<b>Расписание</b>: Не настроено (уведомления каждые 24 часа)\n"
    
    profile_text += "\n" + "─" * 20 + "\n"

    # 5. Подписка
    profile_text += "\n<b>💳 Подписка</b>\n"
    
    if subscription:
        if subscription.status == "trial":
            # Лимит триала = 3 тренировки
            remaining_workouts = 3 - (subscription.trial_workouts_used or 0)
            profile_text += (
                f"<b>Статус:</b> Пробный период "
                f"({max(0, remaining_workouts)} бесплатных тренировок осталось)\n"
            )
        elif subscription.status == "active":
            expires_str = subscription.expires_at.strftime("%d.%m.%Y")
            profile_text += f"<b>Статус:</b> Активна до {expires_str}\n"
        else:
             profile_text += f"<b>Статус:</b> Неактивна\n"
    else:
        profile_text += "<b>Статус:</b> Нет подписки\n"


    return profile_text


@router.message(F.text.in_(["👤 Профиль", "Профиль", "профиль"]))
async def show_profile(message: Message, session: AsyncSession, state: FSMContext):
    """
    Обработчик нажатия кнопки Профиль (Reply кнопка).
    Сбрасывает состояние.
    """
    await state.clear()
    user = await get_user_by_telegram_id(session, message.from_user.id)
    
    if not user:
        await message.answer(
            "❌ Вы еще не зарегистрированы. Используйте /start для регистрации.",
            reply_markup=get_main_menu_keyboard()
        )
        return

    # Получаем расписание и подписку
    schedule_list = await get_user_schedule(session, user.id)
    subscription = await subscription_requests.get_subscription_by_user_id(
        session, user.id
    )

    # Форматируем профиль
    profile_text = format_full_profile_text(user, schedule_list, subscription)

    await message.answer(
        profile_text,
        reply_markup=get_profile_inline_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "edit_profile")
async def edit_profile_callback(query: CallbackQuery, state: FSMContext):
    """
    Обработчик нажатия кнопки "Изменить" в профиле.
    Запускает процесс регистрации заново.
    """
    # Используем функцию из start.py для начала процесса
    await start_registration_process(query, state)


@router.message(F.text == "💳 Приобрести подписку")
async def acquire_subscription_handler(message: Message, session: AsyncSession):
    """Обрабатывает нажатие кнопки 'Приобрести подписку'."""
    user = await get_user_by_telegram_id(session, message.from_user.id)
    if not user:
        await message.answer("Не удалось найти ваш профиль. Пожалуйста, перезапустите бота /start.", show_alert=True)
        return

    subscription = await subscription_requests.get_subscription_by_user_id(session, user.id)

    if subscription and subscription.status == "active" and subscription.expires_at > datetime.now():
        await message.answer(
            "У вас уже есть активная подписка. Вы уверены, что хотите ее продлить?",
            reply_markup=get_extend_subscription_keyboard()
        )
    else:
        await message.answer(
            "Выберите удобный для вас тариф:",
            reply_markup=get_payment_keyboard()
        )


@router.callback_query(F.data == "confirm_extend_subscription")
async def confirm_extend_subscription_handler(query: CallbackQuery, session: AsyncSession):
    """Отправляет инвойс на оплату для продления подписки."""
    try:
        await query.bot.send_invoice(
            chat_id=query.from_user.id,
            title="Продление подписки",
            description="Продление доступа ко всем функциям на 1 месяц.",
            payload="monthly_subscription", # Такой же payload, чтобы обработчик сработал
            currency="XTR",
            prices=[LabeledPrice(label="Продление подписки на 1 месяц", amount=50)],
            start_parameter="one-month-subscription-extend",
        )
        await query.message.delete() # Удаляем сообщение с кнопками "Да/Нет"
    except Exception as e:
        logging.error(f"Failed to send extend invoice to user {query.from_user.id}: {e}", exc_info=True)
        await query.message.edit_text(
            "❌ Произошла ошибка при создании счета. Пожалуйста, попробуйте еще раз."
        )
    finally:
        await query.answer()


@router.callback_query(F.data == "cancel_extend_subscription")
async def cancel_extend_subscription_handler(query: CallbackQuery):
    """Отменяет продление подписки."""
    await query.message.edit_text("Продление подписки отменено.")
    await query.answer()