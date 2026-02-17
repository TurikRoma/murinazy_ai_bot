import json
import re
from pathlib import Path


def normalize_name(name: str) -> str:
    """Приводит название упражнения к единому формату для сопоставления."""
    name = name.lower()
    name = name.replace("ё", "е")
    name = re.sub(r'["«»\'()`’]', "", name)
    name = name.replace("лежа", "лёжа")
    name = name.replace("сидя (тренажер)", "сидя(тренажер)")
    name = name.replace("стоя (гантели)", "стоя(гантели)")
    name = re.sub(r"\s+", " ", name).strip()
    return name


def prepare_exercises_json():
    """
    Собирает данные из трех JSON-файлов в один результирующий.
    """
    base_dir = Path(__file__).resolve().parent.parent
    exercises_by_type_path = base_dir / "exercises_by_muscle_and_type.json"
    exercises_with_ids_path = base_dir / "exercises_with_ids.json"
    instructions_path = base_dir / "instaractions.json"
    output_path = base_dir / "combined_exercises.json"

    with open(exercises_by_type_path, "r", encoding="utf-8") as f:
        exercises_by_type = json.load(f)

    with open(exercises_with_ids_path, "r", encoding="utf-8") as f:
        exercises_with_ids = json.load(f)

    with open(instructions_path, "r", encoding="utf-8") as f:
        instructions_data = json.load(f)

    # Создаем словари для быстрого поиска по нормализованному имени
    ids_lookup = {
        normalize_name(ex["name"]): {"file_id": ex["file_id"], "type": ex["type"]}
        for ex in exercises_with_ids
    }
    instructions_lookup = {
        normalize_name(key): value for key, value in instructions_data.items()
    }

    result_data = {}

    for muscle_group, equipment_types in exercises_by_type.items():
        result_data[muscle_group] = {}
        for equipment_type, exercise_names in equipment_types.items():
            result_data[muscle_group][equipment_type] = []
            for exercise_name in exercise_names:
                normalized_name = normalize_name(exercise_name)

                media_info = ids_lookup.get(normalized_name)
                instruction = instructions_lookup.get(normalized_name, None)

                exercise_obj = {
                    "name": exercise_name,
                    "instruction": instruction,
                    "file_id": media_info["file_id"] if media_info else None,
                    "type": media_info["type"] if media_info else None,
                }
                result_data[muscle_group][equipment_type].append(exercise_obj)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)

    print(f"Результирующий файл сохранен в: {output_path}")


if __name__ == "__main__":
    prepare_exercises_json()
