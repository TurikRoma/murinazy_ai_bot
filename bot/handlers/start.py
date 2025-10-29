from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ContentType

from bot.keyboards.registration import get_start_keyboard, get_gender_keyboard
from bot.states.registration import RegistrationStates
from bot.config.settings import settings

router = Router()

# ID видео-кружка для приветствия
WELCOME_VIDEO_NOTE_ID = "DQACAgIAAxkBAAMmaOQAAR5O_W30odYD9bVfen7eb2jmAAKmhgACLXcgS1jSe-JEwg0VNgQ"


async def start_registration_process(query: CallbackQuery, state: FSMContext):
    """
    Универсальная функция для начала или перезапуска процесса регистрации.
    """
    await state.set_state(RegistrationStates.waiting_for_gender)
    await query.message.edit_text(
        "Для начала выбери свой пол:",
        reply_markup=get_gender_keyboard()
    )
    await query.answer()


@router.message(CommandStart())
async def command_start(message: Message):
    """
    Обработчик команды /start.
    Отправляет приветственное сообщение и кнопку 'Начать'.
    """
    # TODO: Добавить отправку video_note согласно @vision.md
    await message.answer_video_note(WELCOME_VIDEO_NOTE_ID)
    await message.answer(
        "Привет! Я твой персональный AI-тренер. "
        "Готов начать путь к своей лучшей форме?",
        reply_markup=get_start_keyboard(),
    )

@router.callback_query(F.data == "start_registration")
async def start_registration_callback(query: CallbackQuery, state: FSMContext):
    """
    Обработка нажатия кнопки 'Начать' для старта регистрации.
    """
    await start_registration_process(query, state)


# --- Обработчик для получения file_id медиа (только для админа) ---
@router.message(
    lambda message: message.from_user.id == settings.ADMIN_ID,
    F.content_type.in_({ContentType.VIDEO, ContentType.ANIMATION})
)
async def get_media_file_id(message: Message):
    """
    Этот обработчик ловит видео и гифки, отправленные админом,
    и возвращает их file_id.
    """
    file_id = None
    media_type = None

    if message.video:
        file_id = message.video.file_id
        media_type = "video"
    elif message.animation:
        file_id = message.animation.file_id
        media_type = "gif"

    if file_id:
        await message.reply(
            f"<b>Тип:</b> <code>{media_type}</code>\n"
            f"<b>File ID:</b> <code>{file_id}</code>"
        )
# --- Конец обработчика ---