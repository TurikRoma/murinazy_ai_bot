from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup


def get_extend_subscription_keyboard() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру для подтверждения продления подписки."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, продлить", callback_data="confirm_extend_subscription")
    builder.button(text="❌ Отмена", callback_data="cancel_extend_subscription")
    builder.adjust(2)
    return builder.as_markup()
