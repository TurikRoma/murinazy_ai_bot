from pydantic import BaseModel
from typing import List


class PlanSummary(BaseModel):
    periodization_type: str
    split_type: str
    primary_goal: str


class ExercisePlan(BaseModel):
    order: int
    exercise_name: str
    sets: int
    reps: int | str



class WorkoutDayPlan(BaseModel):
    day: int
    focus: str
    warm_up: str
    exercises: List[ExercisePlan]
    cool_down: str


class LLMWorkoutPlan(BaseModel):
    plan_summary: PlanSummary
    workout_plan: List[WorkoutDayPlan]






