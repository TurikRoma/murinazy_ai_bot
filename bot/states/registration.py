from aiogram.fsm.state import StatesGroup, State


class RegistrationStates(StatesGroup):
    """Состояния для процесса регистрации."""
    waiting_for_gender = State()
    waiting_for_age = State()
    waiting_for_height = State()
    waiting_for_current_weight = State()
    waiting_for_fitness_level = State()
    waiting_for_goal = State()
    waiting_for_target_weight = State()
    waiting_for_workout_frequency = State()
    waiting_for_equipment_type = State()
    waiting_for_confirmation = State()



