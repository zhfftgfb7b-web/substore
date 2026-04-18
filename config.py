"""
Конфигурация приложения из переменных окружения
"""
import os
from pathlib import Path
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
    # TODO: Add YooKassa when ИП/company is ready
    # YOOKASSA_SHOP_ID: str = ""
    # YOOKASSA_SECRET_KEY: str = ""
    CRYPTO_PAY_TOKEN: str = ""

    # Manual payment (bank card)
    ADMIN_CARD_NUMBER: str = "2200****1234"
    ADMIN_CARD_OWNER: str = "Имя Фамилия"

    model_config = SettingsConfigDict(
        # .env файл используется только если существует (для локальной разработки)
        env_file=".env" if Path(".env").exists() else None,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # Игнорировать лишние переменные
    )


# Глобальный экземпляр настроек
settings = Settings()
