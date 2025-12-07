from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

async def check_user_subscription(user_id: int, bot: Bot, channels: list[dict]) -> tuple[bool, list[str]]:
    """
    Проверяет подписку пользователя на список каналов.
    
    :param user_id: ID пользователя
    :param bot: Экземпляр бота
    :param channels: Список каналов (должен содержать ключ 'username' или 'id')
    :return: (is_subscribed: bool, missing_channels: list[str]) - статус и список названий каналов, куда не подписан
    """
    missing_channels = []
    
    for channel in channels:
        # Если проверка для канала отключена, пропускаем его
        if not channel.get('check_required', True):
            continue

        chat_id = channel.get('username') or channel.get('id')
        try:
            member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            # Статусы, которые считаются "подписан"
            if member.status not in ("member", "administrator", "creator"):
                missing_channels.append(channel['name'])
        except TelegramBadRequest:
            # Если бот не админ или чат не найден, считаем это как ошибку конфигурации, 
            # но для пользователя лучше пока пропустить или залогировать.
            # В данном случае, если мы не можем проверить, считаем что не подписан (безопасный вариант)
            # или логируем ошибку. Для простоты сейчас добавим в missing.
            # В реальном проде лучше логировать, что бот не админ.
            print(f"Error checking subscription for {chat_id}: Bot might not be admin")
            missing_channels.append(channel['name'])
        except Exception as e:
            print(f"Unexpected error checking subscription for {chat_id}: {e}")
            missing_channels.append(channel['name'])
            
    return len(missing_channels) == 0, missing_channels

