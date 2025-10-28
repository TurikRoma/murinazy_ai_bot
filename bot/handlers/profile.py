from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.handlers.start import start_registration_process
from bot.keyboards.registration import get_profile_reply_keyboard, get_profile_inline_keyboard
from bot.requests.user_requests import get_user_by_telegram_id
from bot.requests.schedule_requests import get_user_schedule
from bot.utils.rank_utils import get_rank_by_score, get_next_rank_threshold

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
    "trainer_style": "Стиль тренера",
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
    "goggins": "Гоггинс",
    "schwarzenegger": "Шварцнегер",
    "coleman": "Колеман",
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


def format_user_profile(user) -> str:
    """
    Форматирует данные пользователя для красивого отображения в профиле.
    """
    profile_text = "<b>👤 Ваш профиль</b>\n\n"
    
    # Отображаем очки и звание в самом верху, красиво оформленные
    user_score = user.score or 0
    user_rank = get_rank_by_score(user_score)
    next_rank_info = get_next_rank_threshold(user_score)
    
    profile_text += f"🏆 <b>Звание:</b> {user_rank}\n"
    profile_text += f"⭐ <b>Очки:</b> {user_score}"
    
    if next_rank_info:
        next_threshold, next_rank = next_rank_info
        points_to_next = next_threshold - user_score
        profile_text += f" (до <b>{next_rank}</b> осталось {points_to_next} очков)"
    
    profile_text += "\n" + "─" * 20 + "\n\n"
    
    # Определяем порядок ключей для красивого вывода
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
        ("trainer_style", user.trainer_style),
    ]
    
    for field_name, value in fields:
        if value is None:
            continue
        
        display_name = HUMAN_READABLE_NAMES.get(field_name, field_name)
        
        # Преобразуем значение для отображения
        if hasattr(value, 'value'):  # Enum
            display_value = HUMAN_READABLE_NAMES.get(value.value, str(value.value))
        else:
            display_value = str(value)
            # Для workout_frequency добавляем текст
            if field_name == "workout_frequency":
                display_value = f"{value} раз(а) в неделю"
            # Для веса и роста добавляем единицы измерения
            elif field_name in ["current_weight", "target_weight"]:
                display_value = f"{value} кг"
            elif field_name == "height":
                display_value = f"{value} см"
        
        profile_text += f"<b>{display_name}</b>: {display_value}\n"
    
    return profile_text


async def format_user_profile_with_schedule(
    user, schedule_list
) -> str:
    """
    Форматирует данные пользователя с расписанием тренировок.
    """
    profile_text = format_user_profile(user)
    
    # Добавляем расписание, если оно есть
    if schedule_list:
        schedule_items = []
        for schedule in schedule_list:
            day_short = DAYS_FULL_TO_SHORT.get(schedule.day.value, schedule.day.value)
            time_str = schedule.notification_time.strftime('%H:%M')
            schedule_items.append(f"{day_short} в {time_str}")
        schedule_str = ", ".join(schedule_items)
        profile_text += f"\n<b>Расписание</b>: {schedule_str}"
    else:
        profile_text += "\n<b>Расписание</b>: Не настроено (уведомления каждые 24 часа)"
    
    return profile_text


@router.message(F.text.in_(["👤 Профиль", "Профиль", "профиль"]))
async def show_profile(message: Message, session: AsyncSession):
    """
    Обработчик нажатия кнопки Профиль (Reply кнопка).
    """
    user = await get_user_by_telegram_id(session, message.from_user.id)
    
    if not user:
        await message.answer(
            "❌ Вы еще не зарегистрированы. Используйте /start для регистрации.",
            reply_markup=get_profile_reply_keyboard()
        )
        return
    
    # Получаем расписание пользователя
    schedule_list = await get_user_schedule(session, user.id)
    
    # Форматируем профиль
    profile_text = await format_user_profile_with_schedule(user, schedule_list)
    
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