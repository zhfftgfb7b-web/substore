"""
Система уведомлений админу
"""
import logging
from aiogram import Bot
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import settings

logger = logging.getLogger(__name__)


async def notify_admin_new_sale_auto(bot: Bot, order):
    """Уведомление о новой автоматической продаже с маржой"""
    try:
        # Рассчитываем маржу если есть cost_price
        margin_text = ""
        if order.product.cost_price:
            margin = order.amount - order.product.cost_price
            margin_text = f"Маржа: ~{margin:,.0f}₽\n"

        await bot.send_message(
            settings.ADMIN_ID,
            f"💰 **Новый заказ #{order.id}**\n\n"
            f"Клиент: @{order.user.username or 'noname'}\n"
            f"Товар: {order.product.emoji} {order.product.name}\n"
            f"Сумма: {order.amount:,.0f}₽ ({order.payment_method.value})\n"
            f"{margin_text}\n"
            f"✅ Ключ выдан автоматически",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Failed to notify admin about auto sale: {e}")


async def notify_admin_new_sale_manual(bot: Bot, order):
    """Уведомление о новой ручной продаже (требует действия)"""
    try:
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="✅ Выполнить", callback_data=f"admin:complete:{order.id}"),
            InlineKeyboardButton(text="❌ Отменить", callback_data=f"admin:cancel:{order.id}")
        )

        email_text = f"Email: {order.apple_id_email or 'не указан'}" if hasattr(order, 'apple_id_email') else ""

        await bot.send_message(
            settings.ADMIN_ID,
            f"⏳ **Заказ требует выполнения #{order.id}**\n\n"
            f"Клиент: @{order.user.username or 'noname'}\n"
            f"Товар: {order.product.emoji} {order.product.name}\n"
            f"{email_text}\n"
            f"Сумма: {order.amount:,.0f}₽ ({order.payment_method.value})\n\n"
            f"Выполни заказ и отметь:",
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Failed to notify admin about manual sale: {e}")


async def notify_admin_manual_payment_pending(bot: Bot, order):
    """Уведомление о ручном переводе на подтверждение"""
    try:
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="✅ Деньги пришли — выдать", callback_data=f"admin:confirm_payment:{order.id}")
        )
        builder.row(
            InlineKeyboardButton(text="❌ Нет поступления — отклонить", callback_data=f"admin:decline_payment:{order.id}")
        )

        from datetime import datetime
        time_str = datetime.utcnow().strftime("%H:%M")

        await bot.send_message(
            settings.ADMIN_ID,
            f"💳 **Проверь поступление #{order.id}**\n\n"
            f"Клиент: @{order.user.username or 'noname'}\n"
            f"Товар: {order.product.emoji} {order.product.name}\n"
            f"Сумма: {order.amount:,.0f}₽\n"
            f"Способ: Перевод на карту {settings.ADMIN_CARD_NUMBER}\n"
            f"Время: {time_str}\n\n"
            f"Проверь поступление на карту и подтверди:",
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Failed to notify admin about manual payment: {e}")


async def notify_admin_low_stock(bot: Bot, product, available_count: int):
    """Уведомление о малом запасе ключей"""
    try:
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="➕ Добавить ключи", callback_data=f"admin:select_product:{product.id}")
        )

        indicator = "🔴" if available_count == 0 else "🟡"

        await bot.send_message(
            settings.ADMIN_ID,
            f"⚠️ **Заканчиваются ключи**\n\n"
            f"{indicator} {product.emoji} {product.name}: {available_count} шт\n\n"
            f"Пополни запас, иначе продукт станет недоступен",
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Failed to notify admin about low stock: {e}")
