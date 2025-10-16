import asyncio
import json
import os
import sys
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# Добавляем корневую директорию проекта в sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.config.settings import settings
from bot.requests.exercise_requests import clear_exercises, add_exercises_bulk
from bot.schemas.exercise import ExerciseCreate


async def main():
    """
    Основная функция для очистки и заполнения базы данных упражнениями
    из файла exercises_by_muscle_and_type.json.
    """
    print("Начинаю процесс заполнения базы данных упражнениями...")

    # Настройка подключения к БД
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # Загрузка данных из JSON
    try:
        with open("exercises_by_muscle_and_type.json", "r", encoding="utf-8") as f:
            all_exercises_data = json.load(f)
        print("✅ JSON-файл с упражнениями успешно загружен.")
    except FileNotFoundError:
        print("❌ Ошибка: Файл 'exercises_by_muscle_and_type.json' не найден.")
        return
    except json.JSONDecodeError:
        print("❌ Ошибка: Не удалось декодировать JSON из файла.")
        return

    exercises_to_create: list[ExerciseCreate] = []
    equipment_map = {"Зал": "gym", "Свой вес": "bodyweight"}

    for muscle_group, equipment_types in all_exercises_data.items():
        for equipment_name, exercise_names in equipment_types.items():
            equipment_type = equipment_map.get(equipment_name)
            if not equipment_type:
                continue

            for name in exercise_names:
                exercises_to_create.append(
                    ExerciseCreate(
                        name=name,
                        muscle_groups=muscle_group,
                        equipment_type=equipment_type,
                    )
                )

    if not exercises_to_create:
        print("⚠️ Упражнения для добавления не найдены.")
        return

    print(f"Найдено {len(exercises_to_create)} упражнений для добавления.")

    async with session_factory() as session:
        # Очистка старых данных
        print("Очищаю таблицу 'exercises'...")
        await clear_exercises(session)
        print("✅ Таблица успешно очищена.")

        # Добавление новых данных
        print("Добавляю новые упражнения в базу данных...")
        await add_exercises_bulk(session, exercises_to_create)
        print(
            "✅ База данных успешно заполнена "
            f"{len(exercises_to_create)} упражнениями."
        )


if __name__ == "__main__":
    # Запускаем скрипт, только если база данных была обновлена
    # (проверка на наличие поля equipment_type в модели Exercise)
    # В реальных условиях, это бы контролировалось миграциями
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"\n❌ Произошла критическая ошибка: {e}")
        print("👉 Убедитесь, что вы применили миграции базы данных (Alembic).")





