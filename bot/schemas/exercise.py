from pydantic import BaseModel
from database.models import EquipmentTypeEnum


class ExerciseCreate(BaseModel):
    name: str
    muscle_groups: str
    equipment_type: EquipmentTypeEnum
