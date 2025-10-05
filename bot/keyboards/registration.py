from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_gender_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора пола."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Мужской", callback_data="gender_male"),
                InlineKeyboardButton(text="Женский", callback_data="gender_female"),
            ]
        ]
    )


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
    """Создает клавиатуру для выбора цели тренировок."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Набор мышечной массы", callback_data="goal_mass_gain")],
            [InlineKeyboardButton(text="Похудение", callback_data="goal_weight_loss")],
            [InlineKeyboardButton(text="Поддержание формы", callback_data="goal_maintenance")],
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
    """Создает клавиатуру для выбора типа оборудования."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Тренажерный зал", callback_data="equip_gym")],
            [InlineKeyboardButton(text="Собственный вес", callback_data="equip_bodyweight")],
        ]
    )
