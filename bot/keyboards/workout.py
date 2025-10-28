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


def get_start_workout_keyboard(workout_id: int) -> InlineKeyboardMarkup:
    """
    Возвращает клавиатуру для начала тренировки (начать/пропустить).
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="▶️ Начать выполнение", callback_data=f"start_workout_{workout_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Пропустить", callback_data=f"workout_skipped_{workout_id}"
                ),
            ]
        ]
    )
    return keyboard


def get_exercise_navigation_keyboard(
    workout_id: int, current_index: int, total_exercises: int
) -> InlineKeyboardMarkup:
    """
    Возвращает клавиатуру для навигации в процессе тренировки.
    """
    buttons = []

    # Если это не последнее упражнение, добавляем кнопку "Следующее"
    if current_index < total_exercises - 1:
        next_button = InlineKeyboardButton(
            text="Следующее упражнение ➡️", callback_data="next_exercise"
        )
        # Кнопка "Завершить" есть всегда, но с разным текстом
        finish_button = InlineKeyboardButton(
            text="⏹️ Завершить досрочно", callback_data=f"finish_workout_{workout_id}"
        )
        buttons.append([next_button])
        buttons.append([finish_button])
    else:
        # На последнем упражнении только кнопка завершения
        finish_button = InlineKeyboardButton(
            text="✅ Завершить тренировку", callback_data=f"finish_workout_{workout_id}"
        )
        buttons.append([finish_button])

    return InlineKeyboardMarkup(inline_keyboard=buttons)
