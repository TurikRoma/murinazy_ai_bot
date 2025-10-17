from pydantic_settings import BaseSettings, SettingsConfigDict

DAYS_OF_WEEK_RU_FULL = {
    "Пн": "понедельник",
    "Вт": "вторник",
    "Ср": "среда",
    "Чт": "четверг",
    "Пт": "пятница",
    "Сб": "суббота",
    "Вс": "воскресенье",
}



class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    
    # Telegram Bot
    BOT_TOKEN: str
    
    # Database
    DATABASE_URL: str
    REDIS_URL: str
    
    # LLM
    PROXY_API_URL: str
    PROXY_API_KEY: str
    
    # App Settings
    WORKOUT_COOLDOWN_HOURS: int = 12
    LOG_LEVEL: str = "INFO"


settings = Settings()
