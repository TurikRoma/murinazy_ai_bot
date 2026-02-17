from aiogram import Router
from . import (
    start,
    registration,
    profile,
    workout,
    admin,
    payment,
    playlists,
)

# Порядок роутеров важен
routers = [
    admin.router,
    start.router,
    registration.router,
    profile.router,
    payment.router,
    playlists.router,
    workout.router,
]

# Главный роутер для всех обработчиков
main_router = Router()

# Регистрируем все роутеры
main_router.include_router(start.router)
main_router.include_router(registration.router)
main_router.include_router(profile.router)
main_router.include_router(payment.router)
main_router.include_router(playlists.router)
main_router.include_router(workout.router)
