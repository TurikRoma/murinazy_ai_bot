from aiogram.fsm.state import State, StatesGroup


class ChatState(StatesGroup):
    chatting = State()
