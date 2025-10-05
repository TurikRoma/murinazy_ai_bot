# bot/middlewares/db.py

# Строки 1-6: Импорты
# Импортируем стандартные типы Python для аннотаций, чтобы сделать код более читаемым.
from typing import Callable, Dict, Any, Awaitable

# Импортируем классы из aiogram, необходимые для создания middleware.
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
# Импортируем "фабрику сессий" из SQLAlchemy для создания подключений к БД.
from sqlalchemy.ext.asyncio import async_sessionmaker

# Строка 9: Объявление класса
# Мы создаем наш собственный класс DbSessionMiddleware и указываем, что он наследуется
# от BaseMiddleware. Это значит, что наш класс теперь является полноценным middleware для aiogram.
class DbSessionMiddleware(BaseMiddleware):

    # Строки 12-15: Конструктор __init__
    # Этот метод вызывается один раз при запуске бота.
    # Он принимает 'session_pool' — нашу "фабрику сессий" из database/connection.py —
    # и сохраняет ее внутри объекта middleware для дальнейшего использования.
    def __init__(self, session_pool: async_sessionmaker):
        super().__init__()
        self.session_pool = session_pool

    # Строки 17-23: Магический метод __call__
    # Это самая главная часть. aiogram будет вызывать этот метод автоматически
    # для каждого входящего события (сообщения, нажатия кнопки и т.д.).
    # handler: Это следующий обработчик в цепочке (другой middleware или наш хэндлер).
    # event: Само событие (например, объект Message).
    # data: Словарь, который "путешествует" вместе с событием. Мы положим в него сессию.
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:

        # Строка 24: Создание сессии
        # 'async with' создает новое, свежее подключение (сессию) к базе данных
        # и гарантирует, что оно будет автоматически и безопасно закрыто после
        # выполнения кода внутри блока, даже если произойдет ошибка.
        async with self.session_pool() as session:

            # Строка 25: "Прокидывание" сессии в data
            # Это ключевой момент! Мы добавляем в словарь 'data' нашу созданную сессию
            # под ключом "session". Теперь она доступна во всех последующих хэндлерах.
            data["session"] = session

            # Строка 26: Вызов следующего обработчика
            # Мы вызываем следующий обработчик (например, наш хэндлер process_age),
            # передавая ему событие и обновленный словарь 'data' с сессией.
            return await handler(event, data)