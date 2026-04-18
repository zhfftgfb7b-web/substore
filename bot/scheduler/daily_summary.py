"""
Ежедневная сводка для админа (APScheduler job)
"""
import logging
from aiogram import Bot

from database import crud
from database.models import DeliveryTypeEnum
from config import settings

logger = logging.getLogger(__name__)


async def send_daily_summary_job(bot: Bot):
    """
    Отправить ежедневную сводку админу в 21:00 UTC
    Запускается раз в день через APScheduler
    """
    try:
        from database.engine import get_db_engine
        db_engine = get_db_engine()

        async for session in db_engine.get_session():
            # Статистика за сегодня
            stats_today = await crud.get_stats_today(session)

            # Топ товар дня
            top_products = await crud.get_top_products(session, limit=1)
            top_product_text = "Нет продаж"
            if top_products:
                product, sales_count, revenue = top_products[0]
                top_product_text = f"{product.emoji} {product.name} ({sales_count} продаж)"

            # Остатки ключей
            products = await crud.get_all_products(session, active_only=True)
            keys_status_lines = []
            low_stock_warning = ""

            for product in products:
                if product.delivery_type == DeliveryTypeEnum.auto:
                    stats = await crud.get_key_stats(session, product.id)
                    available = stats["available"]

                    if available <= 3:
                        emoji = "🔴" if available == 0 else "🟡"
                        keys_status_lines.append(f"{emoji} {product.emoji} {product.name}: {available} шт")

            if keys_status_lines:
                low_stock_warning = "\n\n⚠️ **Нужно пополнить:**\n" + "\n".join(keys_status_lines)
            else:
                low_stock_warning = "\n\n✅ Все остатки в норме, пополнять не надо"

            # Формируем сообщение
            summary_text = (
                f"📊 **Итоги дня**\n\n"
                f"💰 Продажи: {stats_today['orders_today']} заказов на {stats_today['revenue_today']:,.0f}₽\n"
                f"👥 Новых клиентов: {stats_today['users_today']}\n\n"
                f"🏆 Топ товар дня: {top_product_text}"
                f"{low_stock_warning}"
            )

            # Отправляем админу
            await bot.send_message(
                settings.ADMIN_ID,
                summary_text,
                parse_mode="Markdown"
            )

            logger.info(f"Daily summary sent to admin {settings.ADMIN_ID}")

    except Exception as e:
        logger.error(f"Error in send_daily_summary_job: {e}", exc_info=True)
