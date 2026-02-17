import asyncio
import os
import sys
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from dotenv import load_dotenv
from sqlalchemy import select
from aiogram.client.default import DefaultBotProperties

# Добавляем корневую папку проекта в sys.path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from database.connection import async_session_maker
from database.models import Exercise


async def verify_exercises():
    """
    Отправляет все упражнения из базы данных в Telegram для проверки.
    """
    load_dotenv()
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        print("Токен бота не найден. Пожалуйста, добавьте BOT_TOKEN в ваш .env файл.")
        return

    chat_id = 970281922  # ID вашего чата для проверки
    bot = Bot(token=bot_token, default=DefaultBotProperties(parse_mode="HTML"))

    print("Начинаю отправку упражнений для проверки...")

    async with async_session_maker() as session:
        result = await session.execute(select(Exercise).order_by(Exercise.id))
        exercises = result.scalars().all()

        if not exercises:
            print("В базе данных нет упражнений для проверки.")
            await bot.session.close()
            return

        for i, exercise in enumerate(exercises):
            caption = (
                f"<b>Упражнение #{i + 1} (ID: {exercise.id})</b>\n\n"
                f"<b>Название:</b> {exercise.name}\n"
                f"<b>Группа мышц:</b> {exercise.muscle_groups}\n"
                f"<b>Тип оборудования:</b> {exercise.equipment_type.value}\n\n"
                f"<b>Инструкция:</b>\n{exercise.instructions or 'Нет инструкции'}"
            )

            media_id = exercise.video_id or exercise.gif_id
            media_type = "video" if exercise.video_id else "gif"

            try:
                if media_id:
                    if media_type == "video":
                        await bot.send_video(chat_id=chat_id, video=media_id, caption=caption)
                    elif media_type == "gif":
                        await bot.send_animation(chat_id=chat_id, animation=media_id, caption=caption)
                else:
                    await bot.send_message(chat_id=chat_id, text=caption + "\n\n<i>(Медиафайл отсутствует)</i>")
                
                print(f"[+] Отправлено: {exercise.name} ({exercise.muscle_groups})")

            except TelegramBadRequest as e:
                print(f"[!] Ошибка отправки '{exercise.name}': {e}")
                await bot.send_message(chat_id=chat_id, text=f"Ошибка с упражнением: {exercise.name}\n{e}")
            except Exception as e:
                print(f"[!] Непредвиденная ошибка с '{exercise.name}': {e}")
            
            # Задержка для избежания лимитов Telegram
            await asyncio.sleep(2)

    await bot.session.close()
    print(f"\nПроверка завершена. Отправлено {len(exercises)} упражнений.")


if __name__ == "__main__":
    asyncio.run(verify_exercises())
