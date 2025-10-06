from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot.keyboards.registration import get_start_keyboard, get_gender_keyboard
from bot.states.registration import RegistrationStates

router = Router()

@router.message(CommandStart())
async def command_start(message: Message):
    """
    Обработчик команды /start.
    Отправляет приветственное сообщение и кнопку 'Начать'.
    """
    # TODO: Добавить отправку video_note согласно @vision.md
    await message.answer(
        "Привет! Я твой персональный AI-тренер. "
        "Готов начать путь к своей лучшей форме?",
        reply_markup=get_start_keyboard(),
    )

@router.callback_query(F.data == "start_registration")
async def start_registration(query: CallbackQuery, state: FSMContext):
    """
    Обработка нажатия кнопки 'Начать' для старта регистрации.
    Запрашивает пол пользователя.
    """
    await state.set_state(RegistrationStates.waiting_for_gender)
    await query.message.edit_text(
        "Для начала выбери свой пол:",
        reply_markup=get_gender_keyboard()
    )
    await query.answer()
