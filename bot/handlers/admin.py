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
    get_manage_products_keyboard,
    get_product_actions_keyboard,
    get_users_menu_keyboard,
    get_user_actions_keyboard,
)
from config import settings
from database import crud
from database.models import DeliveryTypeEnum

logger = logging.getLogger(__name__)

router = Router(name="admin")


def is_admin(user_id: int) -> bool:
    """Проверка является ли пользователь админом"""
    return user_id == settings.ADMIN_ID


async def get_dashboard_text(session: AsyncSession) -> str:
    """Получить текст дэшборда с мини-статистикой"""
    try:
        # Статистика за сегодня
        stats_today = await crud.get_stats_today(session)

        # Остатки ключей с индикаторами
        products = await crud.get_all_products(session, active_only=False)
        keys_status_lines = []

        for product in products:
            if product.delivery_type == DeliveryTypeEnum.auto:
                stats = await crud.get_key_stats(session, product.id)
                available = stats["available"]

                # Индикаторы: 🟢 >3, 🟡 1-3, 🔴 0
                if available > 3:
                    indicator = "🟢"
                elif available > 0:
                    indicator = "🟡"
                else:
                    indicator = "🔴"

                keys_status_lines.append(f"{indicator} {product.emoji} {product.name}: {available} шт")

        keys_status = "\n".join(keys_status_lines) if keys_status_lines else "Нет товаров с автовыдачей"

        return (
            "🛠 **Панель администратора SubStore**\n\n"
            f"📊 **Статистика сегодня:**\n"
            f"💰 Продажи: {stats_today['revenue_today']:,.0f}₽ ({stats_today['orders_today']} заказов)\n"
            f"👥 Новых клиентов: {stats_today['users_today']}\n\n"
            f"📦 **Остаток ключей:**\n{keys_status}"
        )
    except Exception as e:
        logger.error(f"Error in get_dashboard_text: {e}", exc_info=True)
        return "🛠 **Панель администратора SubStore**\n\nВыберите действие:"


@router.message(Command("admin"))
async def cmd_admin(message: Message, session: AsyncSession):
    """Команда /admin - вход в админ-панель"""
    if not is_admin(message.from_user.id):
        # Silent drop - не раскрываем существование админки
        return

    # Получаем мини-статистику для дэшборда
    dashboard_text = await get_dashboard_text(session)

    await message.answer(
        dashboard_text,
        reply_markup=get_admin_menu_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "admin:menu")
async def show_admin_menu(callback: CallbackQuery, session: AsyncSession):
    """Показать админ меню"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    # Получаем обновлённый дэшборд
    dashboard_text = await get_dashboard_text(session)

    await callback.message.edit_text(
        dashboard_text,
        reply_markup=get_admin_menu_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


# ==================== ORDERS ====================

@router.callback_query(F.data == "admin:orders")
async def show_orders_menu(callback: CallbackQuery, session: AsyncSession):
    """Показать меню заказов с фильтрами"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    try:
        # Получаем статистику по заказам
        from database.models import OrderStatusEnum

        # Заказы требующие действия (paid + manual delivery)
        pending_orders = await crud.get_pending_manual_orders(session)

        # Заказы выполненные сегодня
        from datetime import datetime, timedelta
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        all_orders_today = await crud.get_orders_by_status(session, OrderStatusEnum.delivered, limit=None)
        delivered_today = [o for o in all_orders_today if o.delivered_at and o.delivered_at >= today_start]

        orders_text = (
            "📋 **Заказы**\n\n"
            f"🆕 Требуют действия: {len(pending_orders)}\n"
            f"✅ Сегодня выполнено: {len(delivered_today)}\n\n"
            f"Выберите фильтр:"
        )

        # Клавиатура с фильтрами
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton

        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text=f"🆕 Требуют действия ({len(pending_orders)})", callback_data="admin:orders:pending")
        )
        builder.row(
            InlineKeyboardButton(text=f"✅ Сегодня выполнено ({len(delivered_today)})", callback_data="admin:orders:today")
        )
        builder.row(
            InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:menu")
        )

        await callback.message.edit_text(
            orders_text,
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Error in show_orders_menu: {e}", exc_info=True)
        await callback.answer("❌ Ошибка загрузки заказов", show_alert=True)


@router.callback_query(F.data == "admin:orders:pending")
async def show_pending_orders(callback: CallbackQuery, session: AsyncSession):
    """Показать заказы требующие ручной обработки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    try:
        orders = await crud.get_pending_manual_orders(session)

        if not orders:
            await callback.message.edit_text(
                "📦 **Заказы требующие действия**\n\n"
                "Нет заказов ✅",
                reply_markup=get_back_to_menu_keyboard()
            )
            await callback.answer()
            return

        orders_text = f"📦 **Заказов к обработке:** {len(orders)}\n\n"

        for order in orders[:10]:  # Показываем первые 10
            apple_email = f"\n📧 {order.apple_id_email}" if order.apple_id_email else ""

            orders_text += (
                f"🆔 **Заказ #{order.id}**\n"
                f"👤 @{order.user.username or 'noname'}\n"
                f"📦 {order.product.emoji} {order.product.name}\n"
                f"💰 {order.amount:,.0f}₽{apple_email}\n"
                f"📅 {order.created_at.strftime('%d.%m %H:%M')}\n\n"
            )

        await callback.message.edit_text(
            orders_text,
            reply_markup=get_admin_order_keyboard(orders[0].id) if orders else get_back_to_menu_keyboard(),
            parse_mode="Markdown"
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Error in show_pending_orders: {e}", exc_info=True)
        await callback.answer("❌ Ошибка загрузки заказов", show_alert=True)


@router.callback_query(F.data == "admin:orders:today")
async def show_today_orders(callback: CallbackQuery, session: AsyncSession):
    """Показать заказы выполненные сегодня"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    try:
        from database.models import OrderStatusEnum
        from datetime import datetime

        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        all_orders = await crud.get_orders_by_status(session, OrderStatusEnum.delivered, limit=None)
        orders_today = [o for o in all_orders if o.delivered_at and o.delivered_at >= today_start]

        if not orders_today:
            await callback.message.edit_text(
                "📦 **Заказы выполненные сегодня**\n\n"
                "Нет заказов",
                reply_markup=get_back_to_menu_keyboard()
            )
            await callback.answer()
            return

        total_revenue = sum(float(o.amount) for o in orders_today)

        orders_text = f"✅ **Выполнено сегодня:** {len(orders_today)}\n"
        orders_text += f"💰 Выручка: {total_revenue:,.0f}₽\n\n"

        for order in orders_today[:10]:  # Показываем первые 10
            orders_text += (
                f"#{order.id} {order.product.emoji} {order.product.name} — {order.amount:,.0f}₽\n"
                f"@{order.user.username or 'noname'} ({order.delivered_at.strftime('%H:%M')})\n\n"
            )

        await callback.message.edit_text(
            orders_text,
            reply_markup=get_back_to_menu_keyboard(),
            parse_mode="Markdown"
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Error in show_today_orders: {e}", exc_info=True)
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
    """Обработка ввода ключей (текст или .txt файл)"""
    if not is_admin(message.from_user.id):
        return

    try:
        data = await state.get_data()
        product_id = data["product_id"]

        keys = []

        # Проверяем, есть ли прикрепленный документ
        if message.document:
            # Поддержка .txt файлов
            if not message.document.file_name.endswith('.txt'):
                await message.answer("❌ Поддерживаются только .txt файлы")
                return

            # Скачиваем файл
            file = await message.bot.get_file(message.document.file_id)
            file_content = await message.bot.download_file(file.file_path)

            # Читаем содержимое
            text_content = file_content.read().decode('utf-8')
            keys = [line.strip() for line in text_content.split("\n") if line.strip()]

        elif message.text:
            # Парсим ключи из текста сообщения
            keys = [line.strip() for line in message.text.split("\n") if line.strip()]

        else:
            await message.answer("❌ Отправьте ключи текстом или .txt файлом")
            return

        if not keys:
            await message.answer("❌ Не найдено ни одного ключа")
            return

        # Добавляем ключи (дубликаты автоматически фильтруются в CRUD)
        added_count = await crud.add_keys_to_pool(session, product_id, keys)

        await state.clear()

        # Получаем обновленную статистику
        stats = await crud.get_key_stats(session, product_id)

        # Рассылка waitlist — уведомляем ожидающих клиентов
        from datetime import datetime, timedelta
        waitlist = await crud.get_waitlist_for_product(session, product_id)

        if waitlist:
            notified_count = 0
            product = await crud.get_product_by_id(session, product_id)

            for entry in waitlist:
                try:
                    # Формируем время ожидания
                    wait_time = datetime.utcnow() - entry.requested_at
                    hours_ago = int(wait_time.total_seconds() / 3600)
                    time_text = f"{hours_ago} час{'а' if 1 < hours_ago < 5 else 'ов'} назад" if hours_ago > 0 else "только что"

                    from aiogram.utils.keyboard import InlineKeyboardBuilder
                    from aiogram.types import InlineKeyboardButton

                    builder = InlineKeyboardBuilder()
                    builder.row(
                        InlineKeyboardButton(text="🛒 Купить сейчас", callback_data=f"buy:{product_id}")
                    )
                    builder.row(
                        InlineKeyboardButton(text="⏳ Не сейчас", callback_data="catalog")
                    )

                    await message.bot.send_message(
                        entry.user.telegram_id,
                        f"🎉 **{product.name} снова в наличии!**\n\n"
                        f"Вы интересовались {product.emoji} {product.name}\n"
                        f"{time_text}. Сейчас в наличии {stats['available']} шт.\n\n"
                        f"💰 Цена: {product.price:,.0f}₽\n"
                        f"⚡️ Выдача моментально",
                        reply_markup=builder.as_markup(),
                        parse_mode="Markdown"
                    )
                    notified_count += 1

                except Exception as e:
                    logger.error(f"Failed to notify waitlist user {entry.user.telegram_id}: {e}")

            # Помечаем как уведомленных
            if notified_count > 0:
                await crud.mark_waitlist_notified(session, [e.id for e in waitlist])

                await message.answer(
                    f"✅ Добавлено ключей: {added_count}\n"
                    f"📦 Теперь в наличии: {stats['available']} шт\n\n"
                    f"📬 Уведомлено клиентов: {notified_count}",
                    reply_markup=get_admin_menu_keyboard()
                )
                return

        await message.answer(
            f"✅ Добавлено ключей: {added_count}\n"
            f"📦 Теперь в наличии: {stats['available']} шт",
            reply_markup=get_admin_menu_keyboard()
        )

    except Exception as e:
        logger.error(f"Error in process_keys_input: {e}", exc_info=True)
        await message.answer("❌ Ошибка добавления ключей")
        await state.clear()


# ==================== STATISTICS ====================

@router.callback_query(F.data == "admin:stats")
async def show_statistics(callback: CallbackQuery, session: AsyncSession):
    """Показать детальную статистику"""
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

        # Топ-продукты
        top_products = await crud.get_top_products(session, limit=5)
        top_products_text = "\n🏆 **Топ-продукты:**\n"
        for i, (product, sales_count, revenue) in enumerate(top_products, 1):
            top_products_text += f"{i}. {product.emoji} {product.name} — {sales_count} продаж ({revenue:,.0f}₽)\n"

        if not top_products:
            top_products_text = "\n🏆 **Топ-продукты:**\nПока нет продаж\n"

        # Разбивка по способам оплаты
        payment_breakdown = await crud.get_payment_methods_breakdown(session)
        total_revenue = sum(item["revenue"] for item in payment_breakdown.values())

        payment_text = "\n💳 **По способам оплаты:**\n"
        if payment_breakdown:
            # Названия методов для отображения
            method_names = {
                "crypto": "CryptoBot",
                "manual": "Ручной перевод",
                "stars": "Telegram Stars"
            }

            for method, data in payment_breakdown.items():
                method_name = method_names.get(method, method)
                percentage = (data["revenue"] / total_revenue * 100) if total_revenue > 0 else 0
                payment_text += f"• {method_name}: {percentage:.0f}% ({data['revenue']:,.0f}₽)\n"
        else:
            payment_text += "Пока нет оплат\n"

        # Остаток ключей
        products = await crud.get_all_products(session, active_only=False)
        keys_stats_text = "\n🔑 **Остаток ключей:**\n"

        for product in products:
            if product.delivery_type == DeliveryTypeEnum.auto:
                stats = await crud.get_key_stats(session, product.id)
                emoji = "🟢" if stats["available"] > 10 else "🟡" if stats["available"] > 3 else "🔴"
                keys_stats_text += f"{emoji} {product.name}: {stats['available']} шт\n"

        stats_text = (
            "📊 **Статистика SubStore**\n\n"
            f"👥 Всего пользователей: {total_users}\n"
            f"📦 Всего заказов: {total_orders}\n\n"
            f"**Сегодня:**\n"
            f"• Новых пользователей: {stats_today['users_today']}\n"
            f"• Заказов: {stats_today['orders_today']}\n"
            f"• Выручка: {stats_today['revenue_today']:,.0f}₽\n\n"
            f"**Текущий месяц:**\n"
            f"• Выручка: {stats_month['revenue_month']:,.0f}₽"
            f"{top_products_text}"
            f"{payment_text}"
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


# ==================== MANAGE PRODUCTS ====================

@router.callback_query(F.data == "admin:products")
async def show_products_list(callback: CallbackQuery, session: AsyncSession):
    """Показать список продуктов для управления"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    try:
        products = await crud.get_all_products(session, active_only=False)

        # Формируем список продуктов с индикаторами
        product_lines = ["📦 **Товары в каталоге**\n"]

        for product in products:
            if product.delivery_type == DeliveryTypeEnum.auto:
                stats = await crud.get_key_stats(session, product.id)
                available = stats["available"]

                # Индикаторы: 🟢 >3, 🟡 1-3, 🔴 0
                if available > 3:
                    indicator = "🟢"
                elif available > 0:
                    indicator = "🟡"
                else:
                    indicator = "🔴"

                product_lines.append(
                    f"{indicator} {product.emoji} {product.name:<30} В наличии: {available} шт"
                )
            else:
                # Manual продукты
                product_lines.append(
                    f"⚪ {product.emoji} {product.name:<30} manual"
                )

        products_text = "\n".join(product_lines)

        await callback.message.edit_text(
            products_text + "\n\nВыберите продукт для управления:",
            reply_markup=get_manage_products_keyboard(products),
            parse_mode="Markdown"
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Error in show_products_list: {e}", exc_info=True)
        await callback.answer("❌ Ошибка загрузки продуктов", show_alert=True)


@router.callback_query(F.data.startswith("admin:manage_product:"))
async def show_product_actions(callback: CallbackQuery, session: AsyncSession):
    """Показать действия над продуктом с детальной статистикой"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    try:
        product_id = int(callback.data.split(":")[2])
        product = await crud.get_product_by_id(session, product_id)

        if not product:
            await callback.answer("❌ Продукт не найден", show_alert=True)
            return

        # Получаем статистику продукта
        product_stats = await crud.get_product_stats(session, product_id)

        # Формируем текст карточки
        status = "🟢 Активен" if product.is_active else "🔴 Выключен"

        card_text = f"{product.emoji} **{product.name}**\n\n"
        card_text += f"💰 Цена: {product.price:,.0f}₽\n"

        # Показываем себестоимость если задана
        if product.cost_price:
            card_text += f"🏷 Себестоимость: {product.cost_price:,.0f}₽\n"
            margin_per_item = product.price - product.cost_price
            card_text += f"📈 Маржа: {margin_per_item:,.0f}₽ за шт.\n"

        # Остаток для auto-продуктов
        if product.delivery_type == DeliveryTypeEnum.auto:
            keys_stats = await crud.get_key_stats(session, product_id)
            card_text += f"📦 В наличии: {keys_stats['available']} шт\n"

        # Статистика продаж
        card_text += f"📊 Продано всего: {product_stats['total_sold']} шт\n"

        if product_stats['total_sold'] > 0:
            card_text += f"💵 Выручка: {product_stats['revenue']:,.0f}₽\n"
            if product.cost_price:
                card_text += f"💰 Общая маржа: {product_stats['margin']:,.0f}₽\n"

        card_text += f"\n📅 Длительность: {product.duration_days} дней\n"
        card_text += f"📦 Доставка: {product.delivery_type.value}\n"
        card_text += f"{status}\n\n"
        card_text += "Выберите действие:"

        await callback.message.edit_text(
            card_text,
            reply_markup=get_product_actions_keyboard(product_id, product.is_active),
            parse_mode="Markdown"
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Error in show_product_actions: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("admin:toggle_product:"))
async def toggle_product(callback: CallbackQuery, session: AsyncSession):
    """Включить/выключить продукт"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    try:
        product_id = int(callback.data.split(":")[2])
        new_status = await crud.toggle_product_active(session, product_id)

        status_text = "включен ✅" if new_status else "выключен ❌"
        await callback.answer(f"Продукт {status_text}", show_alert=True)

        # Обновляем отображение продукта
        await show_product_actions(callback, session)

    except Exception as e:
        logger.error(f"Error in toggle_product: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("admin:change_price:"))
async def start_change_price(callback: CallbackQuery, state: FSMContext):
    """Начать процесс изменения цены"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    try:
        product_id = int(callback.data.split(":")[2])

        await state.update_data(product_id=product_id)
        await state.set_state(AdminStates.waiting_new_price)

        await callback.message.edit_text(
            "💰 **Изменение цены**\n\n"
            "Введите новую цену в рублях (например: 199 или 299.50):"
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Error in start_change_price: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)


@router.message(AdminStates.waiting_new_price)
async def process_new_price(message: Message, session: AsyncSession, state: FSMContext):
    """Обработка новой цены продукта"""
    if not is_admin(message.from_user.id):
        return

    try:
        data = await state.get_data()
        product_id = data["product_id"]

        # Парсим цену
        try:
            from decimal import Decimal
            new_price = Decimal(message.text.strip())

            if new_price <= 0:
                await message.answer("❌ Цена должна быть больше 0")
                return

        except Exception:
            await message.answer("❌ Неверный формат цены. Введите число (например: 199 или 299.50)")
            return

        # Обновляем цену
        await crud.update_product_price(session, product_id, new_price)

        await state.clear()

        await message.answer(
            f"✅ Цена обновлена: {new_price}₽",
            reply_markup=get_admin_menu_keyboard()
        )

    except Exception as e:
        logger.error(f"Error in process_new_price: {e}", exc_info=True)
        await message.answer("❌ Ошибка обновления цены")
        await state.clear()


@router.callback_query(F.data.startswith("admin:product_history:"))
async def show_product_history(callback: CallbackQuery, session: AsyncSession):
    """Показать историю продаж продукта"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    try:
        product_id = int(callback.data.split(":")[2])
        product = await crud.get_product_by_id(session, product_id)

        if not product:
            await callback.answer("❌ Продукт не найден", show_alert=True)
            return

        # Получаем историю продаж
        sales_history = await crud.get_product_sales_history(session, product_id, limit=15)

        if not sales_history:
            await callback.message.edit_text(
                f"📋 **История продаж**\n{product.emoji} {product.name}\n\n"
                "Пока нет продаж",
                reply_markup=InlineKeyboardBuilder()
                .row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin:manage_product:{product_id}"))
                .as_markup(),
                parse_mode="Markdown"
            )
            await callback.answer()
            return

        # Формируем текст истории
        history_text = f"📋 **История продаж (последние 15)**\n{product.emoji} {product.name}\n\n"

        for order in sales_history:
            username = f"@{order.user.username}" if order.user.username else "noname"
            delivered_date = order.delivered_at.strftime("%d.%m %H:%M") if order.delivered_at else "?"
            history_text += f"#{order.id} • {order.amount:,.0f}₽ • {username}\n"
            history_text += f"    📅 {delivered_date}\n\n"

        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton

        keyboard = InlineKeyboardBuilder()
        keyboard.row(InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin:manage_product:{product_id}"))

        await callback.message.edit_text(
            history_text,
            reply_markup=keyboard.as_markup(),
            parse_mode="Markdown"
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Error in show_product_history: {e}", exc_info=True)
        await callback.answer("❌ Ошибка загрузки истории", show_alert=True)


# ==================== MANAGE USERS ====================

@router.callback_query(F.data == "admin:users")
async def show_users_menu(callback: CallbackQuery):
    """Показать меню управления пользователями"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    await callback.message.edit_text(
        "👥 **Управление пользователями**\n\n"
        "Используйте поиск для нахождения пользователя:",
        reply_markup=get_users_menu_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data == "admin:search_user")
async def start_user_search(callback: CallbackQuery, state: FSMContext):
    """Начать поиск пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    await state.set_state(AdminStates.waiting_user_search)

    await callback.message.edit_text(
        "🔍 **Поиск пользователя**\n\n"
        "Введите username (без @) или Telegram ID:"
    )
    await callback.answer()


@router.message(AdminStates.waiting_user_search)
async def process_user_search(message: Message, session: AsyncSession, state: FSMContext):
    """Обработка поиска пользователя"""
    if not is_admin(message.from_user.id):
        return

    try:
        search_term = message.text.strip()

        # Ищем пользователей
        users = await crud.search_users(session, search_term)

        if not users:
            await message.answer(
                "❌ Пользователи не найдены",
                reply_markup=get_users_menu_keyboard()
            )
            await state.clear()
            return

        # Если найден один пользователь - показываем его
        if len(users) == 1:
            user = users[0]
            await show_user_info(message, session, user.id, state)
            return

        # Если найдено несколько - показываем список
        users_text = f"🔍 **Найдено пользователей:** {len(users)}\n\n"
        for user in users[:10]:  # Показываем первых 10
            ban_emoji = "🚫" if user.is_banned else "✅"
            users_text += (
                f"{ban_emoji} @{user.username or 'noname'}\n"
                f"ID: `{user.telegram_id}`\n"
                f"Имя: {user.full_name}\n\n"
            )

        users_text += "\n💡 Введите Telegram ID для просмотра деталей"

        await message.answer(
            users_text,
            reply_markup=get_users_menu_keyboard(),
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Error in process_user_search: {e}", exc_info=True)
        await message.answer("❌ Ошибка поиска")
        await state.clear()


async def show_user_info(message: Message, session: AsyncSession, user_id: int, state: FSMContext):
    """Показать информацию о пользователе"""
    try:
        from database.models import User
        user = await session.get(User, user_id)

        if not user:
            await message.answer("❌ Пользователь не найден")
            await state.clear()
            return

        # Получаем статистику
        orders = await crud.get_user_orders(session, user.id, limit=1000)
        referrals_count = await crud.get_user_referrals_count(session, user.id)

        total_spent = sum(float(o.amount) for o in orders if o.status.value in ["paid", "delivered"])

        ban_status = "🚫 Забанен" if user.is_banned else "✅ Активен"

        user_info = (
            f"👤 **Информация о пользователе**\n\n"
            f"ID: `{user.telegram_id}`\n"
            f"Username: @{user.username or 'нет'}\n"
            f"Имя: {user.full_name}\n"
            f"Статус: {ban_status}\n\n"
            f"📊 **Статистика:**\n"
            f"• Заказов: {len(orders)}\n"
            f"• Потрачено: {total_spent}₽\n"
            f"• Рефералов: {referrals_count}\n"
            f"• Бонусов: {user.referral_bonus}₽\n"
            f"• Зарегистрирован: {user.created_at.strftime('%d.%m.%Y')}\n"
        )

        await message.answer(
            user_info,
            reply_markup=get_user_actions_keyboard(user.id, user.is_banned),
            parse_mode="Markdown"
        )
        await state.clear()

    except Exception as e:
        logger.error(f"Error in show_user_info: {e}", exc_info=True)
        await message.answer("❌ Ошибка загрузки информации")
        await state.clear()


@router.callback_query(F.data.startswith("admin:ban_user:"))
async def ban_user_handler(callback: CallbackQuery, session: AsyncSession):
    """Забанить пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    try:
        user_id = int(callback.data.split(":")[2])
        await crud.ban_user(session, user_id, banned=True)

        await callback.answer("🚫 Пользователь забанен", show_alert=True)
        await callback.message.edit_reply_markup(
            reply_markup=get_user_actions_keyboard(user_id, is_banned=True)
        )

    except Exception as e:
        logger.error(f"Error in ban_user_handler: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("admin:unban_user:"))
async def unban_user_handler(callback: CallbackQuery, session: AsyncSession):
    """Разбанить пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    try:
        user_id = int(callback.data.split(":")[2])
        await crud.ban_user(session, user_id, banned=False)

        await callback.answer("✅ Пользователь разбанен", show_alert=True)
        await callback.message.edit_reply_markup(
            reply_markup=get_user_actions_keyboard(user_id, is_banned=False)
        )

    except Exception as e:
        logger.error(f"Error in unban_user_handler: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("admin:user_orders:"))
async def show_user_orders(callback: CallbackQuery, session: AsyncSession):
    """Показать заказы пользователя"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    try:
        user_id = int(callback.data.split(":")[2])
        from database.models import User
        user = await session.get(User, user_id)

        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        orders = await crud.get_user_orders(session, user.id, limit=20)

        if not orders:
            await callback.answer("У пользователя нет заказов", show_alert=True)
            return

        orders_text = f"📦 **Заказы @{user.username or 'noname'}**\n\n"

        for order in orders:
            status_emoji = {
                "pending": "⏳",
                "paid": "💳",
                "delivered": "✅",
                "cancelled": "❌"
            }.get(order.status.value, "❓")

            orders_text += (
                f"{status_emoji} **Заказ #{order.id}**\n"
                f"{order.product.emoji} {order.product.name}\n"
                f"💰 {order.amount}₽\n"
                f"📅 {order.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            )

        await callback.message.edit_text(
            orders_text,
            reply_markup=get_user_actions_keyboard(user.id, user.is_banned),
            parse_mode="Markdown"
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Error in show_user_orders: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)


# ==================== MANUAL PAYMENT CONFIRMATION ====================

@router.callback_query(F.data.startswith("admin:confirm_payment:"))
async def confirm_manual_payment(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    """Подтвердить ручной платеж"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    try:
        order_id = int(callback.data.split(":")[2])
        order = await crud.get_order_by_id(session, order_id)

        if not order:
            await callback.answer("❌ Заказ не найден", show_alert=True)
            return

        # Помечаем как оплаченный
        await crud.mark_order_paid(session, order_id)

        # Обрабатываем выдачу товара
        from bot.handlers.payment import process_order_delivery

        # Создаем фейковое сообщение для process_order_delivery
        class FakeMessage:
            def __init__(self, chat_id, bot):
                self.chat = type('obj', (object,), {'id': chat_id})()
                self.bot = bot

            async def answer(self, text, **kwargs):
                return await self.bot.send_message(self.chat.id, text, **kwargs)

        fake_msg = FakeMessage(order.user.telegram_id, bot)
        await process_order_delivery(fake_msg, session, order)

        await callback.message.edit_text(
            callback.message.text + "\n\n✅ Платеж подтвержден, товар выдан",
            parse_mode="Markdown"
        )
        await callback.answer("✅ Платеж подтвержден", show_alert=True)

    except Exception as e:
        logger.error(f"Error in confirm_manual_payment: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("admin:decline_payment:"))
async def decline_manual_payment(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    """Отклонить ручной платеж"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    try:
        order_id = int(callback.data.split(":")[2])
        order = await crud.get_order_by_id(session, order_id)

        if not order:
            await callback.answer("❌ Заказ не найден", show_alert=True)
            return

        # Отменяем заказ
        await crud.cancel_order(session, order_id)

        # Уведомляем пользователя
        try:
            await bot.send_message(
                order.user.telegram_id,
                f"❌ Платеж по заказу #{order_id} не подтвержден.\n\n"
                f"Обратитесь в поддержку для уточнения деталей."
            )
        except Exception as e:
            logger.error(f"Failed to notify user {order.user.telegram_id}: {e}")

        await callback.message.edit_text(
            callback.message.text + "\n\n❌ Платеж отклонен",
            parse_mode="Markdown"
        )
        await callback.answer("❌ Платеж отклонен", show_alert=True)

    except Exception as e:
        logger.error(f"Error in decline_manual_payment: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)
