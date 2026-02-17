from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_extend_subscription_keyboard() -> InlineKeyboardMarkup:
    """Возвращает клавиатуру для подтверждения продления подписки."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, продлить", callback_data="confirm_extend_subscription")
    builder.button(text="❌ Отмена", callback_data="cancel_extend_subscription")
    builder.adjust(2)
    return builder.as_markup()


def get_subscription_keyboard(channels: list[dict]) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру с кнопками подписки на каналы и кнопкой проверки.
    
    :param channels: Список словарей вида {"name": str, "link": str, ...}
    """
    buttons = []
    
    # Кнопки для каждого канала
    for channel in channels:
        # Используем имя канала в тексте кнопки для ясности, или просто "Подписаться" если так нужно
        # Пользователь попросил "просто слово подписаться". 
        # Но чтобы различать кнопки, лучше все же указать куда. 
        # Если строго следовать "просто слово подписаться", будет две одинаковые кнопки.
        # Сделаем компромисс: "Подписаться" (но в сообщении выше будет понятно). 
        # Но лучше все-таки добавить эмодзи или имя, если каналов несколько.
        # Сделаю строго "Подписаться", так как это прямой запрос.
        buttons.append([InlineKeyboardButton(text="Подписаться", url=channel['link'])])
        
    # Кнопка проверки
    buttons.append([InlineKeyboardButton(text="✅ Я подписался", callback_data="check_subscription")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)
