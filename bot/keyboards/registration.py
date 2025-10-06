from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_fitness_level_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора уровня подготовки."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Начинающий", callback_data="level_beginner")],
            [InlineKeyboardButton(text="Опыт 1-3 года", callback_data="level_intermediate")],
            [InlineKeyboardButton(text="Опыт >3 лет", callback_data="level_advanced")],
        ]
    )


def get_goal_keyboard() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру для выбора цели."""
    mass_gain_button = InlineKeyboardButton(text="Набор массы", callback_data="goal_mass_gain")
    weight_loss_button = InlineKeyboardButton(text="Похудение", callback_data="goal_weight_loss")
    maintenance_button = InlineKeyboardButton(
        text="Поддержание формы", callback_data="goal_maintenance"
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [mass_gain_button, weight_loss_button],
            [maintenance_button],
        ]
    )


def get_workout_frequency_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора частоты тренировок."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="2 раза в неделю", callback_data="freq_2")],
            [InlineKeyboardButton(text="3 раза в неделю", callback_data="freq_3")],
            [InlineKeyboardButton(text="5 раз в неделю", callback_data="freq_5")],
        ]
    )


def get_equipment_type_keyboard() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру для выбора типа оборудования."""
    gym_button = InlineKeyboardButton(text="Тренажерный зал", callback_data="equip_gym")
    bodyweight_button = InlineKeyboardButton(text="Свой вес", callback_data="equip_bodyweight")
    return InlineKeyboardMarkup(inline_keyboard=[[gym_button, bodyweight_button]])


def get_start_keyboard():
    """Возвращает клавиатуру с кнопкой 'Начать'."""
    start_button = InlineKeyboardButton(text="Начать", callback_data="start_registration")
    return InlineKeyboardMarkup(inline_keyboard=[[start_button]])


def get_gender_keyboard():
    """Возвращает клавиатуру для выбора пола."""
    gender_male = InlineKeyboardButton(text="Мужской", callback_data="gender_male")
    gender_female = InlineKeyboardButton(text="Женский", callback_data="gender_female")
    return InlineKeyboardMarkup(inline_keyboard=[[gender_male, gender_female]])
