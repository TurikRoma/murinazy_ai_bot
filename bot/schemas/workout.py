from pydantic import BaseModel, Field
from typing import List


class LLMWorkoutExercise(BaseModel):
    name: str
    muscle_group: str
    sets: int
    reps: str


class LLMWorkoutSession(BaseModel):
    session: int
    exercises: List[LLMWorkoutExercise]


class LLMWorkoutPlan(BaseModel):
    sessions: List[LLMWorkoutSession]





