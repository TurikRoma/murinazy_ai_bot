import datetime

from sqlalchemy import (
    Integer,
    String,
    DateTime,
    ForeignKey,
    Enum,
    Float,
)
from sqlalchemy.orm import declarative_base, Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import enum


Base = declarative_base()


class TimestampMixin:
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), server_default=func.now()
    )


class GenderEnum(str, enum.Enum):
    male = "male"
    female = "female"


class GoalEnum(str, enum.Enum):
    mass_gain = "mass_gain"
    weight_loss = "weight_loss"
    maintenance = "maintenance"


class FitnessLevelEnum(str, enum.Enum):
    beginner = "beginner"
    intermediate = "intermediate"
    advanced = "advanced"


class EquipmentTypeEnum(str, enum.Enum):
    gym = "gym"
    bodyweight = "bodyweight"


class WorkoutStatusEnum(str, enum.Enum):
    planned = "planned"
    completed = "completed"
    skipped = "skipped"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    gender: Mapped[GenderEnum] = mapped_column(Enum(GenderEnum), nullable=True)
    age: Mapped[int] = mapped_column(Integer, nullable=True)
    height: Mapped[int] = mapped_column(Integer, nullable=True)
    current_weight: Mapped[float] = mapped_column(Float, nullable=True)
    goal: Mapped[GoalEnum] = mapped_column(Enum(GoalEnum), nullable=True)
    target_weight: Mapped[float] = mapped_column(Float, nullable=True)
    fitness_level: Mapped[FitnessLevelEnum] = mapped_column(
        Enum(FitnessLevelEnum), nullable=True
    )
    workout_frequency: Mapped[int] = mapped_column(Integer, nullable=True)
    equipment_type: Mapped[EquipmentTypeEnum] = mapped_column(
        Enum(EquipmentTypeEnum), nullable=True
    )

    workouts: Mapped[list["Workout"]] = relationship("Workout", back_populates="user")


class Exercise(Base):
    __tablename__ = "exercises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=True)
    muscle_groups: Mapped[str] = mapped_column(String, nullable=True)
    video_url: Mapped[str] = mapped_column(String, nullable=True)
    image_url: Mapped[str] = mapped_column(String, nullable=True)
    instructions: Mapped[str] = mapped_column(String, nullable=True)

    workout_exercises: Mapped[list["WorkoutExercise"]] = relationship(
        "WorkoutExercise", back_populates="exercise"
    )


class Workout(Base, TimestampMixin):
    __tablename__ = "workouts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    planned_date: Mapped[datetime.date] = mapped_column(
        DateTime, default=func.now(), server_default=func.now()
    )
    status: Mapped[WorkoutStatusEnum] = mapped_column(
        Enum(WorkoutStatusEnum), default=WorkoutStatusEnum.planned
    )

    user: Mapped["User"] = relationship("User", back_populates="workouts")
    workout_exercises: Mapped[list["WorkoutExercise"]] = relationship(
        "WorkoutExercise", back_populates="workout"
    )


class WorkoutExercise(Base):
    __tablename__ = "workout_exercises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workout_id: Mapped[int] = mapped_column(ForeignKey("workouts.id"), nullable=False)
    exercise_id: Mapped[int] = mapped_column(
        ForeignKey("exercises.id"), nullable=False
    )
    sets: Mapped[int] = mapped_column(Integer, nullable=True)
    reps: Mapped[int] = mapped_column(Integer, nullable=True)
    weight: Mapped[float] = mapped_column(Float, nullable=True)
    rest_time: Mapped[int] = mapped_column(Integer, nullable=True)
    notes: Mapped[str] = mapped_column(String, nullable=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False)

    workout: Mapped["Workout"] = relationship("Workout", back_populates="workout_exercises")
    exercise: Mapped["Exercise"] = relationship(
        "Exercise", back_populates="workout_exercises"
    )
