from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ContentType

from bot.keyboards.registration import get_start_keyboard, get_gender_keyboard
from bot.states.registration import RegistrationStates
from bot.config.settings import settings
import asyncio

router = Router()

# ID видео-кружка для приветствия
WELCOME_VIDEO_NOTE_ID = "DQACAgIAAxkBAAIOU2kF3OKOFqll-EtxVsOKkqt6XGjfAAKrhQACXxYxSDiHASUpgYf2NgQ"


async def start_registration_process(query: CallbackQuery, state: FSMContext):
    """
    Универсальная функция для начала или перезапуска процесса регистрации.
    """
    await state.set_state(RegistrationStates.waiting_for_gender)
    await query.message.answer(
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
    
    await message.answer(
        """🔥 Привет, машина! Я — Murinzy AI, твой новый тренер.
Здесь ты получишь всё, чтобы реально прогрессировать и построить тело своей мечты 💪

Смотри, что тебя ждёт:
• Персональные тренировки под твои цели и уровень.
• AI-тренер, который будет с тобой 24/7 — подскажет, замотивирует и не даст сдаться.
• Hardstyle-плейлисты, чтобы каждая тренировка шла на максимум.
• Отслеживание прогресса — видишь, как растёшь с каждой неделей.
• И система званий — покажи, кто реально работает, а не просто говорит. 

Итак, ты уже готов начать🎥👇""",
    )
    await asyncio.sleep(1)
    await message.answer_video_note(WELCOME_VIDEO_NOTE_ID, reply_markup=get_start_keyboard())

@router.callback_query(F.data == "start_registration")
async def start_registration_callback(query: CallbackQuery, state: FSMContext):
    """
    Обработка нажатия кнопки 'Начать' для старта регистрации.
    """
    await start_registration_process(query, state)


# --- Обработчик для получения file_id медиа (только для админа) ---
@router.message(
    lambda message: message.from_user.id == settings.ADMIN_ID,
    F.content_type.in_({ContentType.VIDEO, ContentType.ANIMATION, ContentType.VIDEO_NOTE})
)
async def get_media_file_id(message: Message):
    """
    Этот обработчик ловит видео, гифки и видео-кружки, отправленные админом,
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
    elif message.video_note:
        file_id = message.video_note.file_id
        media_type = "video_note"

    if file_id:
        await message.reply(
            f"<b>Тип:</b> <code>{media_type}</code>\n"
            f"<b>File ID:</b> <code>{file_id}</code>",
            parse_mode="HTML"
        )
# --- Конец обработчика ---