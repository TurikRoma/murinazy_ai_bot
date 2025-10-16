from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.handlers.start import start_registration_process
from bot.states.registration import RegistrationStates
from bot.utils.validation import validate_age, validate_height, validate_weight
from bot.keyboards.registration import (
    get_fitness_level_keyboard,
    get_goal_keyboard,
    get_workout_frequency_keyboard,
    get_equipment_type_keyboard,
    get_confirmation_keyboard,
    get_post_registration_keyboard,
)
from bot.schemas.user import UserRegistrationSchema
from bot.requests import user_requests
from bot.requests.user_requests import get_user_by_telegram_id
from bot.handlers.workout import send_workout_plan

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


@router.callback_query(RegistrationStates.waiting_for_gender, F.data.startswith("gender_"))
async def process_gender(query: CallbackQuery, state: FSMContext):
    """Обработка выбора пола."""
    gender = query.data.split("_")[1]
    await state.update_data(gender=gender)

    await state.set_state(RegistrationStates.waiting_for_age)
    await query.message.edit_text(
        "Отлично! Теперь введи свой возраст (от 10 до 100 лет)."
    )
    await query.answer()


@router.message(RegistrationStates.waiting_for_age)
async def process_age(message: Message, state: FSMContext):
    """Обработка ввода возраста."""
    age = validate_age(message.text)
    if age is None:
        await message.answer("❌ Некорректный возраст. Попробуй еще раз (от 10 до 100).")
        return

    await state.update_data(age=age)
    await state.set_state(RegistrationStates.waiting_for_height)
    await message.answer("Супер! Теперь введи свой рост в сантиметрах (от 100 до 250).")


@router.message(RegistrationStates.waiting_for_height)
async def process_height(message: Message, state: FSMContext):
    """Обработка ввода роста."""
    height = validate_height(message.text)
    if height is None:
        await message.answer("❌ Некорректный рост. Попробуй еще раз (от 100 до 250 см).")
        return

    await state.update_data(height=height)
    await state.set_state(RegistrationStates.waiting_for_current_weight)
    await message.answer("Принято! Теперь введи свой текущий вес в килограммах (от 30 до 300).")


@router.message(RegistrationStates.waiting_for_current_weight)
async def process_current_weight(message: Message, state: FSMContext):
    """Обработка ввода текущего веса."""
    weight = validate_weight(message.text)
    if weight is None:
        await message.answer("❌ Некорректный вес. Попробуй еще раз (от 30 до 300 кг).")
        return

    await state.update_data(current_weight=weight)
    await state.set_state(RegistrationStates.waiting_for_fitness_level)
    await message.answer(
        "Отлично! Какой у тебя уровень подготовки?",
        reply_markup=get_fitness_level_keyboard(),
    )


@router.callback_query(RegistrationStates.waiting_for_fitness_level, F.data.startswith("level_"))
async def process_fitness_level(query: CallbackQuery, state: FSMContext):
    """Обработка выбора уровня подготовки."""
    level = query.data.split("_")[1]
    await state.update_data(fitness_level=level)
    await state.set_state(RegistrationStates.waiting_for_goal)
    await query.message.edit_text(
        "Почти готово! Какая у тебя основная цель?",
        reply_markup=get_goal_keyboard(),
    )
    await query.answer()


@router.callback_query(RegistrationStates.waiting_for_goal, F.data.startswith("goal_"))
async def process_goal(query: CallbackQuery, state: FSMContext):
    """Обработка выбора цели."""
    goal = "_".join(query.data.split("_")[1:])
    await state.update_data(goal=goal)
    await state.set_state(RegistrationStates.waiting_for_target_weight)
    await query.message.edit_text("Отличный выбор! Какой вес ты хочешь достичь?")
    await query.answer()


@router.message(RegistrationStates.waiting_for_target_weight)
async def process_target_weight(message: Message, state: FSMContext):
    """Обработка ввода целевого веса."""
    weight = validate_weight(message.text)
    if weight is None:
        await message.answer("❌ Некорректный вес. Попробуй еще раз (от 30 до 300 кг).")
        return

    await state.update_data(target_weight=weight)
    await state.set_state(RegistrationStates.waiting_for_workout_frequency)
    await message.answer(
        "Как часто ты планируешь тренироваться?",
        reply_markup=get_workout_frequency_keyboard(),
    )


@router.callback_query(RegistrationStates.waiting_for_workout_frequency, F.data.startswith("freq_"))
async def process_workout_frequency(query: CallbackQuery, state: FSMContext):
    """Обработка выбора частоты тренировок."""
    frequency = int(query.data.split("_")[1])
    await state.update_data(workout_frequency=frequency)
    await state.set_state(RegistrationStates.waiting_for_workout_schedule)
    await query.message.edit_text(
        "Хочешь настроить расписание тренировок? Можно пропустить. Если пропустишь, то я буду отправлять через 24 часа.",
        reply_markup=get_workout_schedule_keyboard(),
    )
    await query.answer()


@router.callback_query(RegistrationStates.waiting_for_workout_schedule, F.data == "schedule_configure")
async def process_workout_schedule_configure(query: CallbackQuery, state: FSMContext):
    """Обработка выбора расписания тренировок."""
    await state.set_state(RegistrationStates.waiting_for_workout_schedule_day)
    await query.message.edit_text(
        "В какие дни ты планируешь тренироваться?",
        reply_markup=get_workout_schedule_day_keyboard(),
    )
    await query.answer()


@router.callback_query(RegistrationStates.waiting_for_workout_schedule, F.data == "schedule_skip")
async def process_workout_schedule(query: CallbackQuery, state: FSMContext):
    """Обработка выбора расписания тренировок."""
    await state.update_data(workout_schedule=None)
    await state.set_state(RegistrationStates.waiting_for_equipment_type)
    await query.message.edit_text(
        "Где ты будешь тренироваться?",
        reply_markup=get_equipment_type_keyboard(),
    )
    await query.answer()


@router.callback_query(RegistrationStates.waiting_for_equipment_type, F.data.startswith("equip_"))
async def process_equipment_type(query: CallbackQuery, state: FSMContext):
    """
    Обработка выбора оборудования и переход к подтверждению.
    """
    equipment = query.data.split("_")[1]
    await state.update_data(equipment_type=equipment)
    await state.set_state(RegistrationStates.waiting_for_confirmation)

    user_data = await state.get_data()
    
    # Формируем красивое сообщение с данными
    summary_text = "Давай проверим все данные:\n\n"
    for key, value in user_data.items():
        # Получаем человекочитаемое название поля
        field_name = HUMAN_READABLE_NAMES.get(key, key)
        # Получаем человекочитаемое значение (если есть в словаре)
        display_value = HUMAN_READABLE_NAMES.get(str(value), value)
        summary_text += f"**{field_name}**: {display_value}\n"
        
    await query.message.edit_text(
        text=summary_text,
        reply_markup=get_confirmation_keyboard()
    )
    await query.answer()


@router.callback_query(RegistrationStates.waiting_for_confirmation, F.data == "confirm_registration")
async def confirm_registration(query: CallbackQuery, state: FSMContext, session: AsyncSession):
    """
    Подтверждение регистрации, сохранение пользователя и завершение.
    """
    user_data_dict = await state.get_data()
    registration_schema = UserRegistrationSchema(**user_data_dict)

    await user_requests.create_or_update_user(
        session=session,
        user_data=registration_schema,
        telegram_id=query.from_user.id,
    )

    await state.clear()

    await query.message.edit_text(
        "🎉 **Поздравляю! Регистрация завершена!**\n\n"
        "Теперь я готовлю для тебя твою первую тренировку. "
        "Нажми кнопку ниже, чтобы получить ее.",
        reply_markup=get_post_registration_keyboard(),
    )
    await query.answer()


@router.callback_query(RegistrationStates.waiting_for_confirmation, F.data == "edit_registration")
async def edit_registration(query: CallbackQuery, state: FSMContext):
    """
    Возврат к началу регистрации для внесения изменений.
    """
    # Используем функцию из start.py для начала процесса
    await start_registration_process(query, state)
    

@router.callback_query(F.data == "get_workout")
async def get_workout_after_registration(query: CallbackQuery, session: AsyncSession):
    """
    Обработчик кнопки "Получить тренировку" после регистрации.
    """
    user = await get_user_by_telegram_id(session, query.from_user.id)
    if user:
        # Для send_workout_plan нужен объект Message, а у нас CallbackQuery.
        # Поэтому передаем query.message.
        await send_workout_plan(query.message, session, user)
    else:
        # На случай, если пользователь как-то нажал кнопку, не будучи в базе
        await query.message.answer("Произошла ошибка. Пожалуйста, попробуйте пройти регистрацию заново.")
        
    await query.answer()
