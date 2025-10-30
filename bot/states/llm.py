from aiogram.fsm.state import State, StatesGroup


class LLMState(StatesGroup):
    processing = State()
