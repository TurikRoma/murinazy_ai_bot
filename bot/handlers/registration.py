from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
from datetime import datetime
import logging

# Устанавливаем русскую локаль для названий дней недели
# locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')

from bot.handlers.start import start_registration_process
from bot.states.registration import RegistrationStates
from bot.utils.validation import validate_age, validate_height, validate_weight, validate_time
from bot.keyboards.registration import (
    get_fitness_level_keyboard,
    get_goal_keyboard,
    get_workout_frequency_keyboard,
    get_equipment_type_keyboard,
    get_confirmation_keyboard,
    get_post_registration_keyboard,
    get_workout_schedule_keyboard,
    get_workout_schedule_day_keyboard,
    get_trainer_style_keyboard,
    get_profile_reply_keyboard,
)
from bot.schemas.user import UserRegistrationSchema
from bot.requests import user_requests
from bot.requests.schedule_requests import create_or_update_user_schedule
from bot.requests.user_requests import get_user_by_telegram_id
from bot.services.workout_service import WorkoutService
from bot.config.settings import DAYS_OF_WEEK_RU_FULL


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

# Словарь для ручного перевода дней недели (независимо от локали)
DAYS_OF_WEEK_RU = {
    'Monday': 'Понедельник', 'Tuesday': 'Вторник', 'Wednesday': 'Среда',
    'Thursday': 'Четверг', 'Friday': 'Пятница', 'Saturday': 'Суббота',
    'Sunday': 'Воскресенье'
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
    """Начало настройки расписания: выбор дней."""
    await state.update_data(selected_days=[], workout_schedule={})
    await state.set_state(RegistrationStates.waiting_for_workout_schedule_day)
    await query.message.edit_text(
        "В какие дни ты планируешь тренироваться?",
        reply_markup=get_workout_schedule_day_keyboard(),
    )
    await query.answer()


@router.callback_query(RegistrationStates.waiting_for_workout_schedule_day, F.data.startswith("day_"))
async def process_day_selection(query: CallbackQuery, state: FSMContext):
    """Обработка выбора/отмены выбора дня недели."""
    day = query.data.split("_")[1]
    user_data = await state.get_data()
    selected_days = user_data.get("selected_days", [])
    frequency = user_data.get("workout_frequency", 0)

    if day in selected_days:
        selected_days.remove(day)
    else:
        if len(selected_days) >= frequency:
            await query.answer(
                "Вы уже выбрали максимальное количество дней. "
                "Чтобы выбрать другой день, сначала отмените выбор одного из уже выбранных.",
                show_alert=True
            )
            return
        selected_days.append(day)

    await state.update_data(selected_days=selected_days)
    await query.message.edit_reply_markup(
        reply_markup=get_workout_schedule_day_keyboard(selected_days)
    )
    await query.answer()


@router.callback_query(RegistrationStates.waiting_for_workout_schedule_day, F.data == "confirm_days")
async def process_confirm_days(query: CallbackQuery, state: FSMContext):
    """Подтверждение выбора дней и переход к вводу времени."""
    user_data = await state.get_data()
    selected_days = user_data.get("selected_days", [])
    frequency = user_data.get("workout_frequency", 0)

    if len(selected_days) != frequency:
        await query.answer(
            f"Пожалуйста, выберите ровно {frequency} дня для тренировок.",
            show_alert=True
        )
        return

    # Сохраняем отсортированный список дней для последовательного опроса
    days_order = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    selected_days.sort(key=days_order.index)
    await state.update_data(selected_days=selected_days)
    
    await state.set_state(RegistrationStates.waiting_for_workout_schedule_time)
    
    first_day_short = selected_days[0]
    first_day_full = DAYS_OF_WEEK_RU_FULL.get(first_day_short, first_day_short).capitalize()
    

    await query.message.edit_text(
        f"Отлично! Теперь введи время для тренировки в <b>{first_day_full}</b>.\n\n"
        "Формат: <code>18:30</code> или просто <code>18</code> (будет 18:00).",
        parse_mode="HTML"
    )
    await query.answer()


@router.message(RegistrationStates.waiting_for_workout_schedule_time)
async def process_time_input(message: Message, state: FSMContext):
    """Обработка ввода времени для каждого выбранного дня."""
    time = validate_time(message.text)
    if time is None:
        await message.answer("❌ Некорректный формат времени. Попробуй еще раз (например, <code>19:00</code> или <code>19</code>).", parse_mode="HTML")
        return

    user_data = await state.get_data()
    selected_days = user_data.get("selected_days", [])
    schedule = user_data.get("workout_schedule", {})
    
    # Определяем, для какого дня вводим время
    current_day_index = len(schedule)
    day = selected_days[current_day_index]
    schedule[day] = time
    
    await state.update_data(workout_schedule=schedule)

    # Если еще остались дни, по которым нужно спросить время
    if len(schedule) < len(selected_days):
        next_day_short = selected_days[len(schedule)]
        next_day_full = DAYS_OF_WEEK_RU_FULL.get(next_day_short, next_day_short).capitalize()
        await message.answer(
            f"Принято! Теперь введи время для тренировки в <b>{next_day_full}</b>.",
            parse_mode="HTML"
        )
    else:
        # Все времена введены, переходим к следующему шагу
        await state.set_state(RegistrationStates.waiting_for_equipment_type)
        await message.answer(
            "Где ты будешь тренироваться?",
            reply_markup=get_equipment_type_keyboard(),
        )


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
    """Обработка выбора оборудования и переход к выбору стиля тренера."""
    equipment = query.data.split("_")[1]
    await state.update_data(equipment_type=equipment)
    await state.set_state(RegistrationStates.waiting_for_trainer_style)
    await query.message.edit_text(
        "Какой стиль AI тренера тебе больше нравится?",
        reply_markup=get_trainer_style_keyboard(),
    )
    await query.answer()


@router.callback_query(RegistrationStates.waiting_for_trainer_style, F.data.startswith("trainer_"))
async def process_trainer_style(query: CallbackQuery, state: FSMContext):
    """Обработка выбора стиля тренера и переход к подтверждению."""
    trainer = query.data.split("_")[1]
    await state.update_data(trainer_style=trainer)
    await state.set_state(RegistrationStates.waiting_for_confirmation)

    user_data = await state.get_data()
    
    # Формируем красивое сообщение с данными
    summary_text = "Давай проверим все данные:\n\n"
    
    # Определяем порядок ключей для красивого вывода
    order = [
        "gender", "age", "height", "current_weight", "fitness_level", 
        "goal", "target_weight", "workout_frequency", "workout_schedule", 
        "equipment_type", "trainer_style"
    ]

    for key in order:
        if key in user_data:
            value = user_data[key]
            if value is None:  # Пропускаем пропущенные шаги (расписание)
                continue
            
            field_name = HUMAN_READABLE_NAMES.get(key, key)
            
            if key == "workout_schedule":
                # Красиво форматируем расписание
                if isinstance(value, dict) and value:
                    schedule_str = ", ".join([f"{day} в {time}" for day, time in value.items()])
                    display_value = schedule_str
                else:
                    continue # не выводим если пусто
            else:
                 display_value = HUMAN_READABLE_NAMES.get(str(value), value)

            summary_text += f"<b>{field_name}</b>: {display_value}\n"
            
    await query.message.edit_text(
        text=summary_text,
        reply_markup=get_confirmation_keyboard(),
        parse_mode="HTML"
    )
    await query.answer()


@router.callback_query(RegistrationStates.waiting_for_confirmation, F.data == "confirm_registration")
async def confirm_registration(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    workout_service: WorkoutService,
):
    """
    Подтверждение регистрации, сохранение пользователя и запуск генерации плана.
    """
    try:
        user_data_dict = await state.get_data()
        registration_schema = UserRegistrationSchema(**user_data_dict)

        # Создаем или обновляем пользователя
        user = await user_requests.create_or_update_user(
            session=session,
            user_data=registration_schema,
            telegram_id=query.from_user.id,
        )

        # Сохраняем расписание, если оно было настроено
        workout_schedule = user_data_dict.get("workout_schedule")
        if user and workout_schedule:
            await create_or_update_user_schedule(
                session=session,
                user_id=user.id,
                schedule_data=workout_schedule,
            )

        await state.clear()
        await query.message.delete()
        # Показываем благодарность и информацию о профиле
        thanks_message = (
            "🙏 <b>Спасибо, что указали свои данные!</b>\n\n"
            "Я сохранил всю информацию в вашем профиле. "
            "Если захотите что-то изменить, просто нажмите кнопку <b>👤 Профиль</b> внизу экрана."
        )
        
        await query.answer()
        
        # Отправляем сообщение с благодарностью и Reply клавиатурой
        await query.message.answer(
            thanks_message,
            parse_mode="HTML",
            reply_markup=get_profile_reply_keyboard()
        )

        # Небольшая пауза перед генерацией плана
        await asyncio.sleep(0.5)

        # Показываем загрузку и начинаем генерацию плана
        loading_message = await query.message.answer(
            "🤖 Создаю для тебя индивидуальный план тренировок на неделю..."
        )

        # Генерация, планирование и получение summary и даты
        result = await workout_service.create_and_schedule_weekly_workout(
            session, user.telegram_id
        )

        logging.info(f"Result from create_and_schedule_weekly_workout for user {user.telegram_id}: {result}")

        if result:
            plan_summary, next_workout_datetime = result

            summary_text = (
                f"<b>Тип программы:</b> {plan_summary.periodization_type}\n"
                f"<b>Сплит:</b> {plan_summary.split_type}\n"
                f"<b>Цель на неделю:</b> {plan_summary.primary_goal}"
            )

            if next_workout_datetime:
                # Ручное форматирование даты для надежности
                day_en = next_workout_datetime.strftime('%A')
                day_ru = DAYS_OF_WEEK_RU.get(day_en, day_en)
                formatted_date = f"{day_ru}, {next_workout_datetime.strftime('%d.%m.%Y в %H:%M')}"

                final_text = (
                    f"✅ <b>Ваш план тренировок на неделю готов!</b>\n\n"
                    f"{summary_text}\n\n"
                    f"🗓️ Ваша следующая тренировка запланирована на <b>{formatted_date}</b>. "
                    "Я пришлю уведомление в назначенное время. Хотите посмотреть план уже сейчас?"
                )
            else:
                final_text = (
                    f"✅ <b>Ваш план тренировок на неделю готов!</b>\n\n"
                    f"{summary_text}\n\n"
                    "На этой неделе запланированных тренировок нет. "
                    "Новый план будет создан в начале следующей недели."
                )

            await loading_message.edit_text(
                final_text,
                reply_markup=get_post_registration_keyboard(),
                parse_mode="HTML"
            )
        else:
            # Если workout_service вернул None
            await loading_message.edit_text(
                "❌ Не удалось создать план тренировок. "
                "Пожалуйста, попробуйте позже или свяжитесь с поддержкой.",
                reply_markup=get_post_registration_keyboard(),
            )

    except Exception as e:
        logging.exception("Error during registration confirmation")
        try:
            await query.message.edit_text(
                "❌ Произошла непредвиденная ошибка при создании вашего плана. "
                "Пожалуйста, попробуйте пройти регистрацию заново через команду /start. "
                "Если проблема повторится, свяжитесь с поддержкой."
            )
        except:
            await query.message.answer(
                "❌ Произошла непредвиденная ошибка при создании вашего плана. "
                "Пожалуйста, попробуйте пройти регистрацию заново через команду /start. "
                "Если проблема повторится, свяжитесь с поддержкой."
            )

    finally:
        await query.answer()


@router.callback_query(RegistrationStates.waiting_for_confirmation, F.data == "edit_registration")
async def edit_registration(query: CallbackQuery, state: FSMContext):
    """
    Возврат к началу регистрации для внесения изменений.
    """
    # Используем функцию из start.py для начала процесса
    await start_registration_process(query, state)
