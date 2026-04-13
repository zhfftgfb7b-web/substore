"""
Обработчики профиля, заказов и реферальной программы
"""
import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.inline import (
    get_back_to_menu_keyboard,
    get_order_status_keyboard,
    get_referral_keyboard,
)
from config import settings
from database import crud

logger = logging.getLogger(__name__)

router = Router(name="profile")


ORDER_STATUS_EMOJI = {
    "pending": "⏳",
    "paid": "💳",
    "delivered": "✅",
    "cancelled": "❌",
}

ORDER_STATUS_TEXT = {
    "pending": "Ожидает оплаты",
    "paid": "Оплачен",
    "delivered": "Доставлен",
    "cancelled": "Отменён",
}


@router.callback_query(F.data == "my_orders")
async def show_my_orders(callback: CallbackQuery, session: AsyncSession):
    """Показать историю заказов пользователя"""
    try:
        user = await crud.get_user_by_telegram_id(session, callback.from_user.id)
        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        # Получаем последние 10 заказов
        orders = await crud.get_user_orders(session, user.id, limit=10)

        if not orders:
            await callback.message.edit_text(
                "📋 **Мои заказы**\n\n"
                "У вас пока нет заказов.\n"
                "Перейдите в каталог чтобы сделать первую покупку!",
                reply_markup=get_back_to_menu_keyboard(),
                parse_mode="Markdown"
            )
            await callback.answer()
            return

        # Формируем список заказов
        orders_text = "📋 **Мои заказы**\n\n"

        for order in orders:
            status_emoji = ORDER_STATUS_EMOJI.get(order.status.value, "❓")
            status_text = ORDER_STATUS_TEXT.get(order.status.value, order.status.value)

            order_date = order.created_at.strftime("%d.%m.%Y %H:%M")

            orders_text += (
                f"{status_emoji} **Заказ #{order.id}**\n"
                f"   {order.product.emoji} {order.product.name}\n"
                f"   💰 {order.amount}₽ • {status_text}\n"
                f"   📅 {order_date}\n\n"
            )

        await callback.message.edit_text(
            orders_text,
            reply_markup=get_back_to_menu_keyboard(),
            parse_mode="Markdown"
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Error in show_my_orders: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при загрузке заказов", show_alert=True)


@router.callback_query(F.data.startswith("show_order_data:"))
async def show_order_delivery_data(callback: CallbackQuery, session: AsyncSession):
    """Показать данные доставленного заказа"""
    try:
        order_id = int(callback.data.split(":")[1])

        order = await crud.get_order_by_id(session, order_id)
        if not order:
            await callback.answer("❌ Заказ не найден", show_alert=True)
            return

        # Проверяем что заказ принадлежит пользователю
        if order.user.telegram_id != callback.from_user.id:
            await callback.answer("❌ Это не ваш заказ", show_alert=True)
            return

        if order.status.value != "delivered" or not order.delivery_data:
            await callback.answer("❌ Данные пока недоступны", show_alert=True)
            return

        # Показываем данные
        await callback.message.answer(
            f"🔑 **Данные заказа #{order.id}**\n\n"
            f"{order.product.emoji} {order.product.name}\n\n"
            f"```\n{order.delivery_data}\n```\n\n"
            f"Спасибо за покупку!",
            parse_mode="Markdown"
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Error in show_order_delivery_data: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data == "referral")
async def show_referral_program(callback: CallbackQuery, session: AsyncSession):
    """Показать реферальную программу"""
    try:
        user = await crud.get_user_by_telegram_id(session, callback.from_user.id)
        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        # Получаем статистику
        referrals_count = await crud.get_user_referrals_count(session, user.id)

        # Формируем реферальную ссылку
        bot_username = settings.BOT_USERNAME
        referral_link = f"https://t.me/{bot_username}?start={user.referral_code}"

        referral_text = (
            "👥 **Реферальная программа**\n\n"
            "🎁 Приглашайте друзей и получайте бонусы!\n\n"
            "💰 **Ваши бонусы:** "
            f"{user.referral_bonus}₽\n"
            f"👤 **Приглашено друзей:** {referrals_count}\n\n"
            "📋 **Как это работает:**\n"
            "• Друг регистрируется по вашей ссылке\n"
            "• Вы получаете 50₽ на бонусный счёт\n"
            "• Бонусы автоматически списываются при покупке\n\n"
            f"**Ваша ссылка:**\n"
            f"`{referral_link}`"
        )

        await callback.message.edit_text(
            referral_text,
            reply_markup=get_referral_keyboard(referral_link),
            parse_mode="Markdown"
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Error in show_referral_program: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)
