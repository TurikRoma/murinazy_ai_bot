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


def get_workout_actions_keyboard(workout_id: int) -> InlineKeyboardMarkup:
    """
    Возвращает клавиатуру с действиями для тренировки (завершить/пропустить).
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Завершил", callback_data=f"workout_completed_{workout_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Пропустил", callback_data=f"workout_skipped_{workout_id}"
                ),
            ]
        ]
    )
    return keyboard
