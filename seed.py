"""
Скрипт для заполнения БД начальными продуктами
"""
import asyncio
import logging
from decimal import Decimal

from database.engine import init_db
from database.models import Base, CategoryEnum, DeliveryTypeEnum, Product
from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


INITIAL_PRODUCTS = [
    {
        "name": "iCloud+ 200GB (Family слот)",
        "category": CategoryEnum.icloud,
        "description": "Семейная подписка Apple iCloud+ 200GB. Вы получите слот в семейной группе. Требуется ваш Apple ID.",
        "price": Decimal("199"),
        "duration_days": 30,
        "delivery_type": DeliveryTypeEnum.manual,
        "emoji": "☁️",
        "sort_order": 1,
    },
    {
        "name": "Apple One Family",
        "category": CategoryEnum.icloud,
        "description": "Семейная подписка Apple One (iCloud+, Apple Music, Apple TV+, Apple Arcade). Слот в семейной группе.",
        "price": Decimal("349"),
        "duration_days": 30,
        "delivery_type": DeliveryTypeEnum.manual,
        "emoji": "🍎",
        "sort_order": 2,
    },
    {
        "name": "VPN-ключ 30 дней",
        "category": CategoryEnum.vpn,
        "description": "Приватный VPN ключ на 30 дней. Работает на всех устройствах. Автоматическая выдача.",
        "price": Decimal("149"),
        "duration_days": 30,
        "delivery_type": DeliveryTypeEnum.auto,
        "emoji": "🔒",
        "sort_order": 3,
    },
    {
        "name": "VPN-ключ 90 дней",
        "category": CategoryEnum.vpn,
        "description": "Приватный VPN ключ на 90 дней. Работает на всех устройствах. Автоматическая выдача.",
        "price": Decimal("349"),
        "duration_days": 90,
        "delivery_type": DeliveryTypeEnum.auto,
        "emoji": "🔒",
        "sort_order": 4,
    },
    {
        "name": "Apple Gift Card $10 USA",
        "category": CategoryEnum.gift_card,
        "description": "Подарочная карта Apple на $10 для американского App Store. Автоматическая выдача кода.",
        "price": Decimal("999"),
        "duration_days": 365,
        "delivery_type": DeliveryTypeEnum.auto,
        "emoji": "🎁",
        "sort_order": 5,
    },
    {
        "name": "Steam Gift Card 500₽",
        "category": CategoryEnum.gift_card,
        "description": "Подарочная карта Steam на 500 рублей. Автоматическая выдача кода.",
        "price": Decimal("549"),
        "duration_days": 365,
        "delivery_type": DeliveryTypeEnum.auto,
        "emoji": "🎮",
        "sort_order": 6,
    },
    {
        "name": "Spotify Premium 1 месяц",
        "category": CategoryEnum.streaming,
        "description": "Подписка Spotify Premium на 1 месяц. Ручная выдача в течение 2 часов.",
        "price": Decimal("199"),
        "duration_days": 30,
        "delivery_type": DeliveryTypeEnum.manual,
        "emoji": "🎵",
        "sort_order": 7,
    },
    {
        "name": "ChatGPT Plus (аккаунт)",
        "category": CategoryEnum.ai,
        "description": "Готовый аккаунт ChatGPT Plus. Автоматическая выдача доступа.",
        "price": Decimal("999"),
        "duration_days": 30,
        "delivery_type": DeliveryTypeEnum.auto,
        "emoji": "🤖",
        "sort_order": 8,
    },
]


async def seed_products():
    """Заполнить БД начальными продуктами"""
    logger.info("Seeding database with initial products...")

    # Инициализация БД
    db_engine = init_db(settings.DATABASE_URL)

    # Создание таблиц
    async with db_engine.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Tables created")

    # Добавление продуктов
    async for session in db_engine.get_session():
        for product_data in INITIAL_PRODUCTS:
            product = Product(**product_data)
            session.add(product)

        await session.commit()
        logger.info(f"Added {len(INITIAL_PRODUCTS)} products")

    await db_engine.dispose()
    logger.info("Database seeding completed!")


if __name__ == "__main__":
    asyncio.run(seed_products())
