from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_payment_keyboard() -> InlineKeyboardMarkup:
    """
    Возвращает клавиатуру с кнопкой для оплаты подписки.
    """
    keyboard = [
        [
            InlineKeyboardButton(
                text="Оплатить 1 месяц (1 ⭐️)", callback_data="buy_subscription"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

