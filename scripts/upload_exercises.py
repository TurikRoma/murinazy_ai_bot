import asyncio
import json
import logging
import os
from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile
from dotenv import load_dotenv

# --- Настройка логирования ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


async def upload_exercises():
    """
    Скрипт для загрузки медиафайлов упражнений в Telegram, получения их file_id
    и сохранения информации в JSON-файл.
    """
    load_dotenv()
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        logging.error("Токен бота не найден. Пожалуйста, добавьте BOT_TOKEN в ваш .env файл.")
        return

    # Используем chat_id, который вы предоставили
    chat_id = 970281922
    bot = Bot(token=bot_token)

    exercises_data = []
    base_path = Path("Murinzy AI упражнения")
    output_file = Path("exercises_with_ids.json")

    if not base_path.is_dir():
        logging.error(f"Папка '{base_path}' не найдена. Убедитесь, что она находится в корне проекта.")
        return

    logging.info(f"Начинаю обработку файлов из папки: {base_path.resolve()}")

    for muscle_group_dir in base_path.iterdir():
        if not muscle_group_dir.is_dir():
            continue

        muscle_group = muscle_group_dir.name
        logging.info(f"Обрабатываю группу мышц: {muscle_group}")

        for file_path in muscle_group_dir.iterdir():
            if not file_path.is_file():
                continue

            exercise_name = file_path.stem
            media_file = FSInputFile(file_path)
            file_id = None
            media_type = None

            try:
                if file_path.suffix.lower() in ['.mp4', '.mov']:
                    sent_message = await bot.send_video(chat_id, media_file)
                    file_id = sent_message.video.file_id
                    media_type = "video"
                elif file_path.suffix.lower() == '.gif':
                    sent_message = await bot.send_animation(chat_id, media_file)
                    file_id = sent_message.animation.file_id
                    media_type = "gif"
                else:
                    logging.warning(f"Пропущен неподдерживаемый формат файла: {file_path.name}")
                    continue

                exercises_data.append({
                    "name": exercise_name.strip(),
                    "file_id": file_id,
                    "muscle_group": muscle_group,
                    "type": media_type
                })
                logging.info(f"[+] Успешно: '{muscle_group} / {exercise_name}'")

            except Exception as e:
                logging.error(f"[!] Ошибка при обработке файла {file_path.name}: {e}")
            
            # Небольшая задержка, чтобы не превышать лимиты Telegram
            await asyncio.sleep(1)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(exercises_data, f, ensure_ascii=False, indent=4)

    logging.info(f"Обработка завершена. Данные сохранены в файл: {output_file.resolve()}")
    await bot.session.close()


if __name__ == "__main__":
    asyncio.run(upload_exercises())
