"""
Добавление актуальных продуктов (апрель 2026)
"""
import asyncio
import logging
from decimal import Decimal

from database.engine import init_db
from database.models import CategoryEnum, DeliveryTypeEnum, Product
from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


NEW_PRODUCTS = [
    # === AI СЕРВИСЫ (самый горячий спрос) ===
    {
        "name": "ChatGPT Plus (1 месяц)",
        "category": CategoryEnum.ai,
        "description": "Подписка ChatGPT Plus с доступом к GPT-4 и DALL-E. Аккаунт готовый к использованию.",
        "price": Decimal("1199"),
        "duration_days": 30,
        "delivery_type": DeliveryTypeEnum.auto,
        "emoji": "🤖",
        "sort_order": 1,
    },
    {
        "name": "Claude Pro (1 месяц)",
        "category": CategoryEnum.ai,
        "description": "Подписка Claude Pro от Anthropic. Доступ к Claude 3 Opus и расширенным лимитам.",
        "price": Decimal("1299"),
        "duration_days": 30,
        "delivery_type": DeliveryTypeEnum.auto,
        "emoji": "🧠",
        "sort_order": 2,
    },
    {
        "name": "Midjourney Standard (1 месяц)",
        "category": CategoryEnum.ai,
        "description": "Подписка Midjourney Standard Plan. Генерация изображений по описанию.",
        "price": Decimal("1499"),
        "duration_days": 30,
        "delivery_type": DeliveryTypeEnum.auto,
        "emoji": "🎨",
        "sort_order": 3,
    },
    {
        "name": "Cursor Pro (1 месяц)",
        "category": CategoryEnum.ai,
        "description": "AI-редактор кода Cursor Pro. Для разработчиков.",
        "price": Decimal("999"),
        "duration_days": 30,
        "delivery_type": DeliveryTypeEnum.auto,
        "emoji": "💻",
        "sort_order": 4,
    },
    {
        "name": "Perplexity Pro (1 месяц)",
        "category": CategoryEnum.ai,
        "description": "AI поисковик Perplexity Pro с неограниченным доступом.",
        "price": Decimal("899"),
        "duration_days": 30,
        "delivery_type": DeliveryTypeEnum.auto,
        "emoji": "🔍",
        "sort_order": 5,
    },

    # === APPLE ЭКОСИСТЕМА ===
    {
        "name": "iCloud+ 50GB (1 месяц)",
        "category": CategoryEnum.icloud,
        "description": "Базовый тариф iCloud+ на 50GB. Семейный слот.",
        "price": Decimal("99"),
        "duration_days": 30,
        "delivery_type": DeliveryTypeEnum.manual,
        "emoji": "☁️",
        "sort_order": 10,
    },
    {
        "name": "iCloud+ 2TB (1 месяц)",
        "category": CategoryEnum.icloud,
        "description": "Премиум тариф iCloud+ на 2TB. Семейный слот.",
        "price": Decimal("499"),
        "duration_days": 30,
        "delivery_type": DeliveryTypeEnum.manual,
        "emoji": "☁️",
        "sort_order": 12,
    },
    {
        "name": "Apple Music Family (1 месяц)",
        "category": CategoryEnum.icloud,
        "description": "Семейная подписка Apple Music до 6 человек. Слот в семейной группе.",
        "price": Decimal("149"),
        "duration_days": 30,
        "delivery_type": DeliveryTypeEnum.manual,
        "emoji": "🎵",
        "sort_order": 13,
    },
    {
        "name": "Apple Gift Card $10 USA",
        "category": CategoryEnum.gift_card,
        "description": "Пополнение баланса Apple ID на $10 для США. Код активации.",
        "price": Decimal("999"),
        "duration_days": 365,
        "delivery_type": DeliveryTypeEnum.auto,
        "emoji": "🍎",
        "sort_order": 14,
    },
    {
        "name": "Apple Gift Card $25 USA",
        "category": CategoryEnum.gift_card,
        "description": "Пополнение баланса Apple ID на $25 для США. Код активации.",
        "price": Decimal("2399"),
        "duration_days": 365,
        "delivery_type": DeliveryTypeEnum.auto,
        "emoji": "🍎",
        "sort_order": 15,
    },

    # === СТРИМИНГ ===
    {
        "name": "Spotify Premium Individual (1 месяц)",
        "category": CategoryEnum.streaming,
        "description": "Индивидуальная подписка Spotify Premium без рекламы.",
        "price": Decimal("199"),
        "duration_days": 30,
        "delivery_type": DeliveryTypeEnum.manual,
        "emoji": "🎵",
        "sort_order": 20,
    },
    {
        "name": "YouTube Premium (1 месяц)",
        "category": CategoryEnum.streaming,
        "description": "YouTube без рекламы + YouTube Music. Готовый аккаунт или семейный слот.",
        "price": Decimal("249"),
        "duration_days": 30,
        "delivery_type": DeliveryTypeEnum.manual,
        "emoji": "▶️",
        "sort_order": 21,
    },
    {
        "name": "Netflix Standard (1 месяц)",
        "category": CategoryEnum.streaming,
        "description": "Netflix Standard план (HD качество, 2 экрана). Готовый аккаунт.",
        "price": Decimal("599"),
        "duration_days": 30,
        "delivery_type": DeliveryTypeEnum.auto,
        "emoji": "🎬",
        "sort_order": 22,
    },

    # === РАЗРАБОТЧИКИ И ДИЗАЙНЕРЫ ===
    {
        "name": "Figma Professional (1 месяц)",
        "category": CategoryEnum.other,
        "description": "Подписка Figma Professional для дизайнеров и команд.",
        "price": Decimal("899"),
        "duration_days": 30,
        "delivery_type": DeliveryTypeEnum.auto,
        "emoji": "🎨",
        "sort_order": 30,
    },
    {
        "name": "Adobe Creative Cloud (1 месяц)",
        "category": CategoryEnum.other,
        "description": "Полный пакет Adobe CC: Photoshop, Illustrator, Premiere Pro и др.",
        "price": Decimal("1999"),
        "duration_days": 30,
        "delivery_type": DeliveryTypeEnum.auto,
        "emoji": "🎨",
        "sort_order": 31,
    },
    {
        "name": "JetBrains All Products (1 месяц)",
        "category": CategoryEnum.other,
        "description": "Доступ ко всем IDE JetBrains: IntelliJ, PyCharm, WebStorm и др.",
        "price": Decimal("1299"),
        "duration_days": 30,
        "delivery_type": DeliveryTypeEnum.auto,
        "emoji": "💻",
        "sort_order": 32,
    },
    {
        "name": "GitHub Copilot (1 месяц)",
        "category": CategoryEnum.ai,
        "description": "AI помощник для программирования от GitHub. Интеграция с VS Code.",
        "price": Decimal("599"),
        "duration_days": 30,
        "delivery_type": DeliveryTypeEnum.auto,
        "emoji": "🐙",
        "sort_order": 6,
    },

    # === ИГРЫ ===
    {
        "name": "Steam Gift Card 500₽",
        "category": CategoryEnum.gift_card,
        "description": "Пополнение кошелька Steam на 500 рублей. Код активации.",
        "price": Decimal("549"),
        "duration_days": 365,
        "delivery_type": DeliveryTypeEnum.auto,
        "emoji": "🎮",
        "sort_order": 40,
    },
    {
        "name": "Steam Gift Card 1000₽",
        "category": CategoryEnum.gift_card,
        "description": "Пополнение кошелька Steam на 1000 рублей. Код активации.",
        "price": Decimal("1049"),
        "duration_days": 365,
        "delivery_type": DeliveryTypeEnum.auto,
        "emoji": "🎮",
        "sort_order": 41,
    },
    {
        "name": "Xbox Game Pass Ultimate (1 месяц)",
        "category": CategoryEnum.other,
        "description": "Xbox Game Pass Ultimate: 100+ игр на Xbox и ПК + EA Play.",
        "price": Decimal("699"),
        "duration_days": 30,
        "delivery_type": DeliveryTypeEnum.auto,
        "emoji": "🎮",
        "sort_order": 42,
    },
    {
        "name": "PlayStation Plus Essential (1 месяц)",
        "category": CategoryEnum.other,
        "description": "PS Plus Essential: онлайн игры + бесплатные игры каждый месяц.",
        "price": Decimal("599"),
        "duration_days": 30,
        "delivery_type": DeliveryTypeEnum.auto,
        "emoji": "🎮",
        "sort_order": 43,
    },

    # === ПРОДУКТИВНОСТЬ ===
    {
        "name": "Notion Plus (1 месяц)",
        "category": CategoryEnum.other,
        "description": "Notion Plus для личного использования. Неограниченное хранилище.",
        "price": Decimal("499"),
        "duration_days": 30,
        "delivery_type": DeliveryTypeEnum.auto,
        "emoji": "📝",
        "sort_order": 50,
    },
    {
        "name": "Zoom Pro (1 месяц)",
        "category": CategoryEnum.other,
        "description": "Zoom Pro: встречи до 30 часов, запись в облако, без ограничений.",
        "price": Decimal("899"),
        "duration_days": 30,
        "delivery_type": DeliveryTypeEnum.auto,
        "emoji": "📹",
        "sort_order": 51,
    },
    {
        "name": "Canva Pro (1 месяц)",
        "category": CategoryEnum.other,
        "description": "Canva Pro: премиум шаблоны, AI инструменты, удаление фона.",
        "price": Decimal("699"),
        "duration_days": 30,
        "delivery_type": DeliveryTypeEnum.auto,
        "emoji": "🎨",
        "sort_order": 52,
    },
]


async def add_new_products():
    """Добавить новые актуальные продукты"""
    logger.info(f"Adding {len(NEW_PRODUCTS)} new products...")

    db_engine = init_db(settings.DATABASE_URL)

    async for session in db_engine.get_session():
        for product_data in NEW_PRODUCTS:
            product = Product(**product_data)
            session.add(product)

        await session.commit()
        logger.info(f"✅ Added {len(NEW_PRODUCTS)} new products")

    await db_engine.dispose()
    logger.info("Done!")


if __name__ == "__main__":
    asyncio.run(add_new_products())
