from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


def get_fitness_level_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора уровня подготовки."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Начинающий", callback_data="level_beginner"),
        InlineKeyboardButton(text="Опыт 1-3 года", callback_data="level_intermediate"),
    )
    builder.row(
        InlineKeyboardButton(text="Опыт >3 лет", callback_data="level_advanced"),
    )
    return builder.as_markup()


def get_goal_keyboard() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру для выбора цели."""
    mass_gain_button = InlineKeyboardButton(text="Набор массы", callback_data="goal_mass_gain")
    weight_loss_button = InlineKeyboardButton(text="Похудение", callback_data="goal_weight_loss")
    maintenance_button = InlineKeyboardButton(
        text="Поддержание формы", callback_data="goal_maintenance"
    )
    builder = InlineKeyboardBuilder()
    builder.row(
        mass_gain_button, weight_loss_button,
    )
    builder.row(
        maintenance_button,
    )
    return builder.as_markup()


def get_workout_frequency_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора частоты тренировок."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="2 раза в неделю", callback_data="freq_2"),
        InlineKeyboardButton(text="3 раза в неделю", callback_data="freq_3"),
    )
    builder.row(
        InlineKeyboardButton(text="5 раз в неделю", callback_data="freq_5"),
    )
    return builder.as_markup()


def get_equipment_type_keyboard() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру для выбора типа оборудования."""
    gym_button = InlineKeyboardButton(text="Тренажерный зал", callback_data="equip_gym")
    bodyweight_button = InlineKeyboardButton(text="Свой вес", callback_data="equip_bodyweight")
    builder = InlineKeyboardBuilder()
    builder.row(
        gym_button, bodyweight_button,
    )
    return builder.as_markup()


def get_start_keyboard() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру с кнопкой 'Начать'."""
    start_button = InlineKeyboardButton(text="Начать", callback_data="start_registration")
    builder = InlineKeyboardBuilder()
    builder.row(
        start_button,
    )
    return builder.as_markup()


def get_gender_keyboard() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру для выбора пола."""
    gender_male = InlineKeyboardButton(text="Мужской", callback_data="gender_male")
    gender_female = InlineKeyboardButton(text="Женский", callback_data="gender_female")
    builder = InlineKeyboardBuilder()
    builder.row(
        gender_male, gender_female,
    )
    return builder.as_markup()


def get_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для подтверждения данных регистрации."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_registration"),
        InlineKeyboardButton(text="✏️ Изменить", callback_data="edit_registration"),
    )
    return builder.as_markup()


def get_post_registration_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру после успешной регистрации."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💪 Получить тренировку", callback_data="get_workout")
    )
    return builder.as_markup()

def get_workout_schedule_day_keyboard(selected_days: list[str] = None) -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора дней недели."""
    if selected_days is None:
        selected_days = []

    days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    builder = InlineKeyboardBuilder()

    row_buttons = []
    for day in days:
        text = f"✅ {day}" if day in selected_days else day
        row_buttons.append(InlineKeyboardButton(text=text, callback_data=f"day_{day}"))

    # Разделяем на ряды по 3-4 кнопки для удобства
    builder.row(*row_buttons[:4])
    builder.row(*row_buttons[4:])

    builder.row(InlineKeyboardButton(text="Подтвердить", callback_data="confirm_days"))
    return builder.as_markup()


def get_workout_schedule_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора расписания тренировок."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Настроить", callback_data="schedule_configure"),
        InlineKeyboardButton(text="Пропустить", callback_data="schedule_skip"),
    )
    return builder.as_markup()


def get_trainer_style_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора стиля AI тренера."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Гоггинс", callback_data="trainer_goggins"),
        InlineKeyboardButton(text="Шварцнегер", callback_data="trainer_schwarzenegger"),
    )
    builder.row(
        InlineKeyboardButton(text="Колеман", callback_data="trainer_coleman"),
    )
    return builder.as_markup()


def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Возвращает главную клавиатуру с кнопками 'Профиль' и 'Приобрести подписку'."""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="👤 Профиль"),
        KeyboardButton(text="💳 Приобрести подписку")
    )
    return builder.as_markup(resize_keyboard=True, persistent=True)


def get_profile_inline_keyboard() -> InlineKeyboardMarkup:
    """Создает Inline клавиатуру для профиля с кнопкой изменения."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✏️ Изменить", callback_data="edit_profile"),
    )
    return builder.as_markup()