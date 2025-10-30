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
    row = []
    if current_index > 0:
        # Эта кнопка не нужна, т.к. мы не удаляем сообщения
        # row.append(InlineKeyboardButton(text="⬅️ Назад", callback_data="prev_exercise"))
        pass

    if current_index < total_exercises - 1:
        row.append(InlineKeyboardButton(text="➡️ Далее", callback_data="next_exercise"))
    
    if row:
        buttons.append(row)

    buttons.append(
        [
            InlineKeyboardButton(
                text="✅ Завершить", callback_data=f"finish_workout_{workout_id}"
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_notification_keyboard(workout_id: int) -> InlineKeyboardMarkup:
    """
    Клавиатура для уведомления о тренировке.
    """
    keyboard = [
        [
            InlineKeyboardButton(
                text="💪 Начать тренировку!", callback_data=f"get_workout_now_{workout_id}"
            )
        ],
        [
            InlineKeyboardButton(text="Пропустить", callback_data=f"workout_skipped_{workout_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
