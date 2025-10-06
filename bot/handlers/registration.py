from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.states.registration import RegistrationStates
from bot.utils.validation import validate_age, validate_height, validate_weight
from bot.keyboards.registration import (
    get_fitness_level_keyboard,
    get_goal_keyboard,
    get_workout_frequency_keyboard,
    get_equipment_type_keyboard,
)
from bot.schemas.user import UserRegistrationSchema
from bot.requests import user_requests

router = Router()


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
    await state.set_state(RegistrationStates.waiting_for_equipment_type)
    await query.message.edit_text(
        "Последний вопрос! Где ты будешь тренироваться?",
        reply_markup=get_equipment_type_keyboard(),
    )
    await query.answer()


@router.callback_query(RegistrationStates.waiting_for_equipment_type, F.data.startswith("equip_"))
async def process_equipment_type(
    query: CallbackQuery, state: FSMContext, session: AsyncSession
):
    """Обработка выбора оборудования и завершение регистрации."""
    equipment = query.data.split("_")[1]
    await state.update_data(equipment_type=equipment)

    user_data_dict = await state.get_data()
    registration_schema = UserRegistrationSchema(**user_data_dict)

    await user_requests.create_or_update_user(
        session=session,
        user_data=registration_schema,
        telegram_id=query.from_user.id,
    )

    await state.clear()

    await query.message.edit_text(
        "🎉 Поздравляю! Регистрация завершена!\n\n"
        "Теперь я готовлю для тебя твою первую тренировку. "
        "Как только она будет готова, я пришлю ее тебе."
    )
    await query.answer()
