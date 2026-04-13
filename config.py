"""
Конфигурация приложения из переменных окружения
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения"""

    # Telegram Bot
    BOT_TOKEN: str
    ADMIN_ID: int
    BOT_USERNAME: str = "SubStoreBot"
    SUPPORT_USERNAME: str = "substore_support"

    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str

    # Payment Systems
    YOOKASSA_SHOP_ID: str = ""
    YOOKASSA_SECRET_KEY: str = ""
    CRYPTO_PAY_TOKEN: str = ""

    # Admin Panel
    ADMIN_PANEL_LOGIN: str = "admin"
    ADMIN_PANEL_PASSWORD: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # Игнорировать лишние переменные
    )


# Глобальный экземпляр настроек
settings = Settings()
