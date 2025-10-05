from aiogram import Router

from . import start, registration

# Главный роутер для всех обработчиков
main_router = Router()

# Регистрируем все роутеры
main_router.include_router(start.router)
main_router.include_router(registration.router)
