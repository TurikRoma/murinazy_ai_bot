from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_workout_now_keyboard(workout_id: int) -> InlineKeyboardMarkup:
    """
    Клавиатура с кнопкой "Получить тренировку сейчас".
    """
    buttons = [
        [
            InlineKeyboardButton(
                text="💪 Получить сейчас",
                callback_data=f"get_workout_now_{workout_id}",
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
