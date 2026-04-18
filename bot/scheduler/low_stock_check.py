"""
Проверка малых запасов ключей (APScheduler job)
"""
import logging
from aiogram import Bot

from database import crud
from database.models import DeliveryTypeEnum
from bot.utils.notifications import notify_admin_low_stock

logger = logging.getLogger(__name__)


async def check_low_stock_job(bot: Bot):
    """
    Проверить остатки ключей и уведомить админа если ≤2 шт
    Запускается каждый час через APScheduler
    """
    try:
        from database.engine import get_db_engine
        db_engine = get_db_engine()

        async for session in db_engine.get_session():
            # Получаем все активные продукты с автовыдачей
            products = await crud.get_all_products(session, active_only=True)

            for product in products:
                if product.delivery_type == DeliveryTypeEnum.auto:
                    stats = await crud.get_key_stats(session, product.id)
                    available = stats["available"]

                    # Уведомляем если ≤2 ключей
                    if available <= 2:
                        logger.warning(f"Low stock for product {product.id} ({product.name}): {available} keys")
                        await notify_admin_low_stock(bot, product, available)

    except Exception as e:
        logger.error(f"Error in check_low_stock_job: {e}", exc_info=True)
