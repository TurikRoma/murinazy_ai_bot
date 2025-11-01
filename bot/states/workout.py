from aiogram.fsm.state import State, StatesGroup


class WorkoutState(StatesGroup):
    in_progress = State()
    waiting_for_feedback = State()
    waiting_for_rating = State()
