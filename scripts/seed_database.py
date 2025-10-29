import asyncio
import json
import sys
from pathlib import Path

# Добавляем корневую папку проекта в sys.path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import async_session_maker
from database.models import Exercise, EquipmentTypeEnum


async def seed_exercises():
    """
    Заполняет базу данных всеми упражнениями из файла combined_exercises.json,
    создавая отдельные записи для разных мышечных групп.
    """
    base_dir = Path(__file__).resolve().parent.parent
    json_path = base_dir / "combined_exercises.json"

    if not json_path.exists():
        print(f"Файл {json_path} не найден.")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    async with async_session_maker() as session:
        # Получаем существующие пары (название, группа), чтобы избежать дублей при повторном запуске
        existing_exercises_result = await session.execute(
            select(Exercise.name, Exercise.muscle_groups)
        )
        existing_exercises = {(name, mg) for name, mg in existing_exercises_result}

        new_exercises_count = 0
        for muscle_group, equipment_types in data.items():
            for equipment_type_str, exercises in equipment_types.items():
                equipment_type = (
                    EquipmentTypeEnum.bodyweight
                    if equipment_type_str == "Свой вес"
                    else EquipmentTypeEnum.gym
                )
                for exercise_data in exercises:
                    exercise_name = exercise_data["name"]

                    # Проверяем на дубликат по паре (название + группа мышц)
                    if (exercise_name, muscle_group) in existing_exercises:
                        continue

                    video_id = None
                    gif_id = None
                    if exercise_data["type"] == "video":
                        video_id = exercise_data["file_id"]
                    elif exercise_data["type"] == "gif":
                        gif_id = exercise_data["file_id"]

                    exercise = Exercise(
                        name=exercise_name,
                        muscle_groups=muscle_group,
                        equipment_type=equipment_type,
                        instructions=exercise_data["instruction"],
                        video_id=video_id,
                        gif_id=gif_id,
                    )
                    session.add(exercise)
                    existing_exercises.add((exercise_name, muscle_group))
                    new_exercises_count += 1

        if new_exercises_count > 0:
            await session.commit()
            print(f"Успешно добавлено {new_exercises_count} новых записей упражнений в базу данных.")
        else:
            print("Новых упражнений для добавления не найдено. База данных уже актуальна.")


if __name__ == "__main__":
    asyncio.run(seed_exercises())
