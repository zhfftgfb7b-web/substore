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


# MVP: Only 4 products for initial launch
# More products will be added based on demand
INITIAL_PRODUCTS = [
    {
        "name": "Apple Gift Card $25 USA",
        "category": CategoryEnum.gift_card,
        "description": (
            "🎁 Подарочная карта Apple на $25 для американского App Store\n\n"
            "✅ Моментальная выдача кода\n"
            "✅ Пополнение Apple ID баланса\n"
            "✅ Оплата подписок и покупок\n"
            "✅ Срок действия не ограничен"
        ),
        "price": Decimal("2800"),
        "duration_days": 365,
        "delivery_type": DeliveryTypeEnum.auto,
        "emoji": "🍎",
        "sort_order": 1,
    },
    {
        "name": "Apple Gift Card 100 TRY Turkey",
        "category": CategoryEnum.gift_card,
        "description": (
            "🎁 Подарочная карта Apple на 100 лир для турецкого App Store\n\n"
            "✅ Моментальная выдача кода\n"
            "✅ Самые низкие цены на подписки\n"
            "✅ Пополнение Apple ID баланса\n"
            "✅ Срок действия не ограничен"
        ),
        "price": Decimal("350"),
        "duration_days": 365,
        "delivery_type": DeliveryTypeEnum.auto,
        "emoji": "🇹🇷",
        "sort_order": 2,
    },
    {
        "name": "ChatGPT Plus",
        "category": CategoryEnum.ai,
        "description": (
            "🤖 Подписка ChatGPT Plus на 1 месяц\n\n"
            "✅ Оплата на ваш email\n"
            "✅ GPT-4 и GPT-4o доступ\n"
            "✅ Приоритетный доступ\n"
            "⏱ Выдача в течение 2 часов"
        ),
        "price": Decimal("2500"),
        "duration_days": 30,
        "delivery_type": DeliveryTypeEnum.manual,
        "emoji": "🤖",
        "sort_order": 3,
    },
    {
        "name": "Spotify Premium",
        "category": CategoryEnum.streaming,
        "description": (
            "🎵 Подписка Spotify Premium на 1 месяц\n\n"
            "✅ Оплата на ваш аккаунт\n"
            "✅ Без рекламы\n"
            "✅ Offline прослушивание\n"
            "⏱ Выдача в течение 2 часов"
        ),
        "price": Decimal("199"),
        "duration_days": 30,
        "delivery_type": DeliveryTypeEnum.manual,
        "emoji": "🎵",
        "sort_order": 4,
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
