from aiogram.fsm.state import State, StatesGroup


class WorkoutState(StatesGroup):
    in_progress = State()
