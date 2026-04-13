"""
Обработчики админ-команд в боте
"""
import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.fsm.states import AdminStates
from bot.keyboards.inline import (
    get_admin_menu_keyboard,
    get_admin_order_keyboard,
    get_admin_products_keyboard,
    get_back_to_menu_keyboard,
    get_broadcast_confirmation_keyboard,
)
from config import settings
from database import crud
from database.models import DeliveryTypeEnum

logger = logging.getLogger(__name__)

router = Router(name="admin")


def is_admin(user_id: int) -> bool:
    """Проверка является ли пользователь админом"""
    return user_id == settings.ADMIN_ID


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Команда /admin - вход в админ-панель"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к админ-панели")
        return

    await message.answer(
        "🔐 **Админ-панель**\n\n"
        "Выберите действие:",
        reply_markup=get_admin_menu_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "admin:menu")
async def show_admin_menu(callback: CallbackQuery):
    """Показать админ меню"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    await callback.message.edit_text(
        "🔐 **Админ-панель**\n\n"
        "Выберите действие:",
        reply_markup=get_admin_menu_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


# ==================== ORDERS ====================

@router.callback_query(F.data == "admin:orders")
async def show_pending_orders(callback: CallbackQuery, session: AsyncSession):
    """Показать заказы требующие ручной обработки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    try:
        orders = await crud.get_pending_manual_orders(session)

        if not orders:
            await callback.message.edit_text(
                "📦 **Заказы**\n\n"
                "Нет заказов требующих обработки ✅",
                reply_markup=get_admin_menu_keyboard()
            )
            await callback.answer()
            return

        orders_text = f"📦 **Заказов к обработке:** {len(orders)}\n\n"

        for order in orders:
            apple_email = f"\n📧 Apple ID: {order.apple_id_email}" if order.apple_id_email else ""

            orders_text += (
                f"🆔 **Заказ #{order.id}**\n"
                f"👤 @{order.user.username or 'noname'} (ID: {order.user.telegram_id})\n"
                f"📦 {order.product.name}\n"
                f"💰 {order.amount}₽{apple_email}\n"
                f"📅 {order.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            )

        await callback.message.edit_text(
            orders_text,
            reply_markup=get_admin_order_keyboard(orders[0].id) if orders else get_admin_menu_keyboard(),
            parse_mode="Markdown"
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Error in show_pending_orders: {e}", exc_info=True)
        await callback.answer("❌ Ошибка загрузки заказов", show_alert=True)


@router.callback_query(F.data.startswith("admin:complete:"))
async def complete_order(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    """Пометить заказ как выполненный"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    try:
        order_id = int(callback.data.split(":")[2])
        order = await crud.get_order_by_id(session, order_id)

        if not order:
            await callback.answer("❌ Заказ не найден", show_alert=True)
            return

        # Помечаем как доставленный
        delivery_data = "Выполнено администратором"
        await crud.deliver_order(session, order_id, delivery_data)

        # Создаём подписку
        await crud.create_subscription(
            session=session,
            user_id=order.user.id,
            product_id=order.product.id,
            order_id=order.id,
            duration_days=order.product.duration_days,
            apple_id_email=order.apple_id_email,
        )

        # Уведомляем пользователя
        try:
            await bot.send_message(
                order.user.telegram_id,
                f"✅ **Ваш заказ #{order.id} выполнен!**\n\n"
                f"{order.product.emoji} {order.product.name}\n\n"
                f"Спасибо за покупку!",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to notify user {order.user.telegram_id}: {e}")

        await callback.answer("✅ Заказ выполнен", show_alert=True)

        # Обновляем список заказов
        await show_pending_orders(callback, session)

    except Exception as e:
        logger.error(f"Error in complete_order: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("admin:cancel:"))
async def cancel_order_admin(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    """Отменить заказ"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    try:
        order_id = int(callback.data.split(":")[2])
        order = await crud.get_order_by_id(session, order_id)

        if not order:
            await callback.answer("❌ Заказ не найден", show_alert=True)
            return

        await crud.cancel_order(session, order_id)

        # Уведомляем пользователя
        try:
            await bot.send_message(
                order.user.telegram_id,
                f"❌ Ваш заказ #{order.id} отменён.\n\n"
                f"Обратитесь в поддержку для уточнения деталей.",
            )
        except Exception as e:
            logger.error(f"Failed to notify user {order.user.telegram_id}: {e}")

        await callback.answer("❌ Заказ отменён", show_alert=True)
        await show_pending_orders(callback, session)

    except Exception as e:
        logger.error(f"Error in cancel_order_admin: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)


# ==================== ADD KEYS ====================

@router.callback_query(F.data == "admin:add_keys")
async def start_add_keys(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Начать процесс добавления ключей"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    try:
        # Получаем все продукты с auto выдачей
        products = await crud.get_all_products(session, active_only=False)
        auto_products = [p for p in products if p.delivery_type == DeliveryTypeEnum.auto]

        if not auto_products:
            await callback.answer("Нет продуктов с автовыдачей", show_alert=True)
            return

        await callback.message.edit_text(
            "🔑 **Добавление ключей**\n\n"
            "Выберите продукт:",
            reply_markup=get_admin_products_keyboard(auto_products),
            parse_mode="Markdown"
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Error in start_add_keys: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("admin:select_product:"))
async def select_product_for_keys(callback: CallbackQuery, state: FSMContext):
    """Выбрать продукт для добавления ключей"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    try:
        product_id = int(callback.data.split(":")[2])

        await state.update_data(product_id=product_id)
        await state.set_state(AdminStates.waiting_keys)

        await callback.message.edit_text(
            "🔑 **Добавление ключей**\n\n"
            "Отправьте ключи (каждый с новой строки):\n\n"
            "Пример:\n"
            "KEY-1234-5678-ABCD\n"
            "KEY-9999-8888-ZZZZ"
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Error in select_product_for_keys: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)


@router.message(AdminStates.waiting_keys)
async def process_keys_input(message: Message, session: AsyncSession, state: FSMContext):
    """Обработка ввода ключей"""
    if not is_admin(message.from_user.id):
        return

    try:
        data = await state.get_data()
        product_id = data["product_id"]

        # Парсим ключи
        keys = [line.strip() for line in message.text.split("\n") if line.strip()]

        if not keys:
            await message.answer("❌ Не найдено ни одного ключа")
            return

        # Добавляем ключи
        added_count = await crud.add_keys_to_pool(session, product_id, keys)

        await state.clear()

        await message.answer(
            f"✅ Добавлено ключей: {added_count}",
            reply_markup=get_admin_menu_keyboard()
        )

    except Exception as e:
        logger.error(f"Error in process_keys_input: {e}", exc_info=True)
        await message.answer("❌ Ошибка добавления ключей")
        await state.clear()


# ==================== STATISTICS ====================

@router.callback_query(F.data == "admin:stats")
async def show_statistics(callback: CallbackQuery, session: AsyncSession):
    """Показать статистику"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    try:
        # Общая статистика
        total_users = await crud.get_total_users(session)
        total_orders = await crud.get_total_orders(session)

        # Статистика за сегодня
        stats_today = await crud.get_stats_today(session)

        # Статистика за месяц
        stats_month = await crud.get_stats_month(session)

        # Остаток ключей
        products = await crud.get_all_products(session, active_only=False)
        keys_stats_text = "\n\n🔑 **Остаток ключей:**\n"

        for product in products:
            if product.delivery_type == DeliveryTypeEnum.auto:
                stats = await crud.get_key_stats(session, product.id)
                emoji = "🟢" if stats["available"] > 10 else "🟡" if stats["available"] > 3 else "🔴"
                keys_stats_text += f"{emoji} {product.name}: {stats['available']} шт.\n"

        stats_text = (
            "📊 **Статистика**\n\n"
            f"👥 **Всего пользователей:** {total_users}\n"
            f"📦 **Всего заказов:** {total_orders}\n\n"
            f"**Сегодня:**\n"
            f"• Новых пользователей: {stats_today['users_today']}\n"
            f"• Заказов: {stats_today['orders_today']}\n"
            f"• Выручка: {stats_today['revenue_today']}₽\n\n"
            f"**Текущий месяц:**\n"
            f"• Выручка: {stats_month['revenue_month']}₽"
            f"{keys_stats_text}"
        )

        await callback.message.edit_text(
            stats_text,
            reply_markup=get_admin_menu_keyboard(),
            parse_mode="Markdown"
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Error in show_statistics: {e}", exc_info=True)
        await callback.answer("❌ Ошибка загрузки статистики", show_alert=True)


# ==================== BROADCAST ====================

@router.callback_query(F.data == "admin:broadcast")
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    """Начать рассылку"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    await state.set_state(AdminStates.waiting_broadcast)

    await callback.message.edit_text(
        "📣 **Рассылка**\n\n"
        "Отправьте текст сообщения для рассылки всем пользователям:"
    )
    await callback.answer()


@router.message(AdminStates.waiting_broadcast)
async def process_broadcast_text(message: Message, state: FSMContext):
    """Обработка текста рассылки"""
    if not is_admin(message.from_user.id):
        return

    try:
        broadcast_text = message.text

        await state.update_data(broadcast_text=broadcast_text)

        # Показываем превью
        await message.answer(
            "📣 **Превью рассылки:**\n\n"
            f"{broadcast_text}\n\n"
            "Отправить это сообщение всем пользователям?",
            reply_markup=get_broadcast_confirmation_keyboard()
        )

    except Exception as e:
        logger.error(f"Error in process_broadcast_text: {e}", exc_info=True)
        await message.answer("❌ Ошибка")
        await state.clear()


@router.callback_query(F.data == "admin:broadcast_confirm")
async def confirm_broadcast(callback: CallbackQuery, session: AsyncSession, state: FSMContext, bot: Bot):
    """Подтвердить и выполнить рассылку"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    try:
        data = await state.get_data()
        broadcast_text = data["broadcast_text"]

        # Получаем всех активных пользователей
        users = await crud.get_all_active_users(session)

        await callback.message.edit_text(
            f"📣 Рассылка запущена...\n"
            f"Пользователей: {len(users)}"
        )

        # Рассылка
        success_count = 0
        failed_count = 0

        for user in users:
            try:
                await bot.send_message(user.telegram_id, broadcast_text)
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to send broadcast to {user.telegram_id}: {e}")
                failed_count += 1

        await state.clear()

        await callback.message.answer(
            f"✅ **Рассылка завершена**\n\n"
            f"Отправлено: {success_count}\n"
            f"Ошибок: {failed_count}",
            reply_markup=get_admin_menu_keyboard()
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Error in confirm_broadcast: {e}", exc_info=True)
        await callback.answer("❌ Ошибка рассылки", show_alert=True)
        await state.clear()
