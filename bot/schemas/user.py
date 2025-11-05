from typing import Optional

from pydantic import BaseModel, Field

from database.models import (
    GenderEnum,
    GoalEnum,
    FitnessLevelEnum,
    EquipmentTypeEnum,
    TrainerStyleEnum,
)


class UserRegistrationSchema(BaseModel):
    gender: Optional[GenderEnum] = None
    age: Optional[int] = Field(None, ge=10, le=100)
    height: Optional[int] = Field(None, ge=100, le=250)
    current_weight: Optional[float] = Field(None, ge=30, le=300)
    fitness_level: Optional[FitnessLevelEnum] = None
    goal: Optional[GoalEnum] = None
    target_weight: Optional[float] = Field(None, ge=30, le=300)
    workout_frequency: Optional[int] = Field(None, ge=1, le=7)
    equipment_type: Optional[EquipmentTypeEnum] = None
    trainer_style: Optional[TrainerStyleEnum] = None
    username: Optional[str] = None
