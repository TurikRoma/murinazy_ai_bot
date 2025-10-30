import datetime

from sqlalchemy import (
    Integer,
    String,
    DateTime,
    ForeignKey,
    Enum,
    Float,
    Time,
    func,
)
from sqlalchemy.orm import declarative_base, Mapped, mapped_column, relationship
from typing import List
from datetime import datetime, time
import enum


Base = declarative_base()


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
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


class TrainerStyleEnum(str, enum.Enum):
    goggins = "goggins"
    schwarzenegger = "schwarzenegger"
    coleman = "coleman"


class WorkoutStatusEnum(str, enum.Enum):
    planned = "planned"
    completed = "completed"
    skipped = "skipped"
    sent = "sent"


class WorkoutScheduleDayEnum(str, enum.Enum):
    понедельник = "понедельник"
    вторник = "вторник"
    среда = "среда"
    четверг = "четверг"
    пятница = "пятница"
    суббота = "суббота"
    воскресенье = "воскресенье"


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
    current_training_week: Mapped[int] = mapped_column(Integer, nullable=True)
    equipment_type: Mapped[EquipmentTypeEnum] = mapped_column(
        Enum(EquipmentTypeEnum), nullable=True
    )
    trainer_style: Mapped[TrainerStyleEnum] = mapped_column(
        Enum(TrainerStyleEnum), nullable=True
    )
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False, server_default="0")

    workouts: Mapped[List["Workout"]] = relationship(
        "Workout", back_populates="user", cascade="all, delete-orphan"
    )
    workout_schedules: Mapped[List["WorkoutSchedule"]] = relationship(
        "WorkoutSchedule", back_populates="user", cascade="all, delete-orphan"
    )
    subscription: Mapped["Subscription"] = relationship(
        "Subscription", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class Exercise(Base):
    __tablename__ = "exercises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=True)
    muscle_groups: Mapped[str] = mapped_column(String, nullable=True)
    equipment_type: Mapped[EquipmentTypeEnum] = mapped_column(
        Enum(EquipmentTypeEnum), nullable=False
    )
    video_id: Mapped[str] = mapped_column(String, nullable=True)
    gif_id: Mapped[str] = mapped_column(String, nullable=True)
    instructions: Mapped[str] = mapped_column(String, nullable=True)

    workout_exercises: Mapped[list["WorkoutExercise"]] = relationship(
        "WorkoutExercise", back_populates="exercise", cascade="all, delete-orphan"
    )


class Workout(Base, TimestampMixin):
    __tablename__ = "workouts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    planned_date: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), server_default=func.now()
    )
    status: Mapped[WorkoutStatusEnum] = mapped_column(
        Enum(WorkoutStatusEnum), default=WorkoutStatusEnum.planned
    )
    warm_up: Mapped[str | None] = mapped_column(String, nullable=True)
    cool_down: Mapped[str | None] = mapped_column(String, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="workouts")
    workout_exercises: Mapped[list["WorkoutExercise"]] = relationship(
        "WorkoutExercise", back_populates="workout", cascade="all, delete-orphan"
    )
    

class WorkoutExercise(Base):
    __tablename__ = "workout_exercises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workout_id: Mapped[int] = mapped_column(ForeignKey("workouts.id", ondelete="CASCADE"), nullable=False)
    exercise_id: Mapped[int] = mapped_column(
        ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False
    )
    sets: Mapped[int] = mapped_column(Integer, nullable=True)
    reps: Mapped[str] = mapped_column(String, nullable=True)
    notes: Mapped[str] = mapped_column(String, nullable=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False)

    workout: Mapped["Workout"] = relationship("Workout", back_populates="workout_exercises")
    exercise: Mapped["Exercise"] = relationship(
        "Exercise", back_populates="workout_exercises"
    )

class WorkoutSchedule(Base):
    __tablename__ = "workout_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    day: Mapped[WorkoutScheduleDayEnum] = mapped_column(Enum(WorkoutScheduleDayEnum), nullable=False)
    notification_time: Mapped[time] = mapped_column(Time, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="workout_schedules")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    status: Mapped[str] = mapped_column(
        String, default="trial"
    )  # Enum: trial, trial_expired, active, expired
    trial_workouts_used: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="subscription") 