from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

router = Router()

PLAYLISTS_TEXT = """
<b>🎵 Наши плейлисты для ваших тренировок:</b>

🎧 <b>SoundCloud:</b> <a href="https://on.soundcloud.com/p54LgD2PaEv93Fb77">Слушать</a>

🎧 <b>Spotify:</b> <a href="https://open.spotify.com/playlist/4ALziZIYYXZ0ZxiejPX3oH?si=wOsOZQ8OTHaVdvmDpDcehA&pi=vMMV7h16Sx6nq">Слушать</a>

🎧 <b>Яндекс.Музыка:</b> <a href="https://music.yandex.ru/users/danilamurin@gmail.com/playlists/1000?utm_medium=copy_link">Слушать</a>

🎧 <b>ВКонтакте:</b> <a href="https://vk.com/music?z=audio_playlist262275660_51&access_key=2852d0e8d48603360d">Слушать</a>
"""

@router.message(F.text.in_(["🎵 Плейлисты", "Плейлисты", "плейлисты"]))
async def show_playlists(message: Message, state: FSMContext):
    """
    Обработчик нажатия кнопки 'Плейлисты'.
    Отправляет сообщение с ссылками на плейлисты и сбрасывает состояние.
    """
    await state.clear()
    await message.answer(
        PLAYLISTS_TEXT,
        parse_mode="HTML",
        disable_web_page_preview=True
    )
