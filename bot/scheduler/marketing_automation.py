"""
Маркетинговая автоматизация и scheduler jobs для повышения конверсии
"""
import logging
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import crud
from database.engine import init_db
from database.models import Order, OrderStatusEnum, Product, Subscription, User

logger = logging.getLogger(__name__)


# ==================== 1. БРОШЕННАЯ КОРЗИНА ====================

async def abandoned_cart_job(bot: Bot):
    """
    Job: Напоминание о брошенных заказах
    Триггер: заказ создан, не оплачен 30 минут → пуш через 2 часа
    """
    try:
        logger.info("Running abandoned cart job...")
        db_engine = init_db(settings.DATABASE_URL)

        async for session in db_engine.get_session():
            # Ищем заказы: pending, создан 2-3 часа назад (30 мин + 2 часа)
            time_from = datetime.utcnow() - timedelta(hours=3)
            time_to = datetime.utcnow() - timedelta(hours=2)

            result = await session.execute(
                select(Order)
                .where(
                    and_(
                        Order.status == OrderStatusEnum.pending,
                        Order.created_at >= time_from,
                        Order.created_at <= time_to,
                    )
                )
            )
            abandoned_orders = result.scalars().all()

            notified = 0
            for order in abandoned_orders:
                try:
                    user_result = await session.execute(
                        select(User).where(User.id == order.user_id)
                    )
                    user = user_result.scalar_one_or_none()

                    product_result = await session.execute(
                        select(Product).where(Product.id == order.product_id)
                    )
                    product = product_result.scalar_one_or_none()

                    if not user or not product:
                        continue

                    builder = InlineKeyboardBuilder()
                    builder.row(
                        InlineKeyboardButton(
                            text="💳 Оплатить сейчас", callback_data=f"buy:{product.id}"
                        )
                    )
                    builder.row(
                        InlineKeyboardButton(text="❓ Помощь", callback_data="support")
                    )
                    builder.row(
                        InlineKeyboardButton(text="⬅️ В каталог", callback_data="catalog")
                    )

                    await bot.send_message(
                        user.telegram_id,
                        f"👋 **Вы выбирали {product.name}**\n\n"
                        f"{product.emoji} {product.name}\n"
                        f"💰 Цена: {product.price:,.0f}₽\n\n"
                        f"Оплата не прошла? Может помочь наш гайд или\n"
                        f"поддержка. Или выберите другой способ:",
                        reply_markup=builder.as_markup(),
                        parse_mode="Markdown",
                    )
                    notified += 1

                except Exception as e:
                    logger.error(f"Failed to send abandoned cart reminder to user {user.telegram_id}: {e}")

            logger.info(f"Abandoned cart job: notified {notified} users")

        await db_engine.dispose()

    except Exception as e:
        logger.error(f"Error in abandoned_cart_job: {e}", exc_info=True)


# ==================== 2. НАПОМИНАНИЕ О ПРОДЛЕНИИ ====================

async def renewal_reminder_job(bot: Bot):
    """
    Job: Напоминание о продлении подписки
    Триггер: за 3 дня до окончания подписки
    """
    try:
        logger.info("Running renewal reminder job...")
        db_engine = init_db(settings.DATABASE_URL)

        async for session in db_engine.get_session():
            # Ищем активные подписки, истекающие через 2-4 дня (окно для уведомления "за 3 дня")
            time_from = datetime.utcnow() + timedelta(days=2)
            time_to = datetime.utcnow() + timedelta(days=4)

            result = await session.execute(
                select(Subscription)
                .where(
                    and_(
                        Subscription.is_active == True,
                        Subscription.renewal_reminder_sent == False,
                        Subscription.expires_at >= time_from,
                        Subscription.expires_at <= time_to,
                    )
                )
            )
            expiring_subscriptions = result.scalars().all()

            notified = 0
            for subscription in expiring_subscriptions:
                try:
                    user_result = await session.execute(
                        select(User).where(User.id == subscription.user_id)
                    )
                    user = user_result.scalar_one_or_none()

                    product_result = await session.execute(
                        select(Product).where(Product.id == subscription.product_id)
                    )
                    product = product_result.scalar_one_or_none()

                    if not user or not product:
                        continue

                    days_left = (subscription.expires_at - datetime.utcnow()).days

                    builder = InlineKeyboardBuilder()
                    builder.row(
                        InlineKeyboardButton(
                            text="✅ Продлить", callback_data=f"buy:{product.id}"
                        )
                    )
                    builder.row(
                        InlineKeyboardButton(
                            text="🚫 Не продлевать", callback_data="catalog"
                        ),
                        InlineKeyboardButton(text="❓ Вопрос", callback_data="support"),
                    )

                    await bot.send_message(
                        user.telegram_id,
                        f"{product.emoji} **Ваша подписка {product.name} истекает через {days_left} дн.**\n\n"
                        f"Продлить на следующий месяц за {product.price:,.0f}₽? Цена\n"
                        f"не менялась.",
                        reply_markup=builder.as_markup(),
                        parse_mode="Markdown",
                    )

                    # Помечаем как отправленное
                    subscription.renewal_reminder_sent = True
                    await session.commit()

                    notified += 1

                except Exception as e:
                    logger.error(f"Failed to send renewal reminder to user {user.telegram_id}: {e}")

            logger.info(f"Renewal reminder job: notified {notified} users")

        await db_engine.dispose()

    except Exception as e:
        logger.error(f"Error in renewal_reminder_job: {e}", exc_info=True)


# ==================== 3. RE-ENGAGEMENT НЕАКТИВНЫХ ====================

async def reengagement_job(bot: Bot):
    """
    Job: Re-engagement неактивных пользователей
    Триггер: не покупал 14 дней
    """
    try:
        logger.info("Running re-engagement job...")
        db_engine = init_db(settings.DATABASE_URL)

        async for session in db_engine.get_session():
            # Ищем пользователей без покупок за последние 14 дней
            cutoff_date = datetime.utcnow() - timedelta(days=14)

            # Пользователи, у которых последний заказ был > 14 дней назад или вообще нет заказов
            result = await session.execute(
                select(User)
                .outerjoin(Order)
                .group_by(User.id)
                .having(
                    (User.created_at < cutoff_date)  # Зарегистрирован давно
                )
            )

            all_users = result.scalars().all()

            # Фильтруем: последний заказ был > 14 дней назад
            inactive_users = []
            for user in all_users:
                last_order_result = await session.execute(
                    select(Order)
                    .where(Order.user_id == user.id)
                    .order_by(Order.created_at.desc())
                    .limit(1)
                )
                last_order = last_order_result.scalar_one_or_none()

                if not last_order or last_order.created_at < cutoff_date:
                    inactive_users.append(user)

            notified = 0
            for user in inactive_users[:100]:  # Ограничиваем 100 в день
                try:
                    builder = InlineKeyboardBuilder()
                    builder.row(
                        InlineKeyboardButton(text="🛒 Каталог", callback_data="catalog")
                    )

                    await bot.send_message(
                        user.telegram_id,
                        f"👋 **Давно не виделись!**\n\n"
                        f"За это время добавили в каталог:\n"
                        f"• 🤖 AI сервисы (ChatGPT, Claude, Cursor)\n"
                        f"• 🍎 Apple Gift Cards\n"
                        f"• 🎮 Игры (PS Plus, Xbox Game Pass)\n\n"
                        f"Смотреть → 🛒 Каталог",
                        reply_markup=builder.as_markup(),
                        parse_mode="Markdown",
                    )
                    notified += 1

                except Exception as e:
                    logger.error(f"Failed to send re-engagement to user {user.telegram_id}: {e}")

            logger.info(f"Re-engagement job: notified {notified} users")

        await db_engine.dispose()

    except Exception as e:
        logger.error(f"Error in reengagement_job: {e}", exc_info=True)


# ==================== 4. WELCOME-СЕРИЯ ====================

async def welcome_day2_job(bot: Bot):
    """
    Job: Welcome-серия день 2 (если не сделал покупку)
    """
    try:
        logger.info("Running welcome day 2 job...")
        db_engine = init_db(settings.DATABASE_URL)

        async for session in db_engine.get_session():
            # Пользователи зарегистрированные 2 дня назад без покупок
            two_days_ago_from = datetime.utcnow() - timedelta(days=2, hours=1)
            two_days_ago_to = datetime.utcnow() - timedelta(days=2)

            result = await session.execute(
                select(User)
                .where(
                    and_(
                        User.created_at >= two_days_ago_from,
                        User.created_at <= two_days_ago_to,
                    )
                )
            )

            new_users = result.scalars().all()

            notified = 0
            for user in new_users:
                # Проверяем есть ли покупки
                orders_result = await session.execute(
                    select(Order)
                    .where(
                        and_(
                            Order.user_id == user.id,
                            Order.status.in_(
                                [OrderStatusEnum.paid, OrderStatusEnum.delivered]
                            ),
                        )
                    )
                )
                has_orders = orders_result.scalar_one_or_none() is not None

                if has_orders:
                    continue  # Уже покупал

                try:
                    builder = InlineKeyboardBuilder()
                    builder.row(
                        InlineKeyboardButton(text="🛒 Каталог", callback_data="catalog")
                    )

                    await bot.send_message(
                        user.telegram_id,
                        f"💡 **Знаете что в SubStore самое популярное?**\n\n"
                        f"🤖 ChatGPT Plus и Claude Pro\n"
                        f"🍎 Apple Gift Cards\n"
                        f"🎵 Spotify и YouTube Premium\n\n"
                        f"Все с моментальной выдачей и низкими ценами!",
                        reply_markup=builder.as_markup(),
                        parse_mode="Markdown",
                    )
                    notified += 1

                except Exception as e:
                    logger.error(f"Failed to send welcome day 2 to user {user.telegram_id}: {e}")

            logger.info(f"Welcome day 2 job: notified {notified} users")

        await db_engine.dispose()

    except Exception as e:
        logger.error(f"Error in welcome_day2_job: {e}", exc_info=True)


async def welcome_day5_job(bot: Bot):
    """
    Job: Welcome-серия день 5 (если всё ещё не купил)
    """
    try:
        logger.info("Running welcome day 5 job...")
        db_engine = init_db(settings.DATABASE_URL)

        async for session in db_engine.get_session():
            # Пользователи зарегистрированные 5 дней назад без покупок
            five_days_ago_from = datetime.utcnow() - timedelta(days=5, hours=1)
            five_days_ago_to = datetime.utcnow() - timedelta(days=5)

            result = await session.execute(
                select(User)
                .where(
                    and_(
                        User.created_at >= five_days_ago_from,
                        User.created_at <= five_days_ago_to,
                    )
                )
            )

            new_users = result.scalars().all()

            notified = 0
            for user in new_users:
                # Проверяем есть ли покупки
                orders_result = await session.execute(
                    select(Order)
                    .where(
                        and_(
                            Order.user_id == user.id,
                            Order.status.in_(
                                [OrderStatusEnum.paid, OrderStatusEnum.delivered]
                            ),
                        )
                    )
                )
                has_orders = orders_result.scalar_one_or_none() is not None

                if has_orders:
                    continue  # Уже покупал

                try:
                    builder = InlineKeyboardBuilder()
                    builder.row(
                        InlineKeyboardButton(text="🛒 Каталог", callback_data="catalog")
                    )

                    await bot.send_message(
                        user.telegram_id,
                        f"🎁 **Специально для вас!**\n\n"
                        f"Скидка 10% на первую покупку.\n\n"
                        f"Промокод: `WELCOME10`\n"
                        f"Действует 48 часов.\n\n"
                        f"Применится автоматически при оплате!",
                        reply_markup=builder.as_markup(),
                        parse_mode="Markdown",
                    )
                    notified += 1

                except Exception as e:
                    logger.error(f"Failed to send welcome day 5 to user {user.telegram_id}: {e}")

            logger.info(f"Welcome day 5 job: notified {notified} users")

        await db_engine.dispose()

    except Exception as e:
        logger.error(f"Error in welcome_day5_job: {e}", exc_info=True)


# ==================== 5. ПЕРСОНАЛЬНЫЕ РЕКОМЕНДАЦИИ ====================

async def recommendations_job(bot: Bot):
    """
    Job: Персональные рекомендации через 2 дня после покупки
    """
    try:
        logger.info("Running recommendations job...")
        db_engine = init_db(settings.DATABASE_URL)

        async for session in db_engine.get_session():
            # Заказы выполненные 2 дня назад
            two_days_ago_from = datetime.utcnow() - timedelta(days=2, hours=1)
            two_days_ago_to = datetime.utcnow() - timedelta(days=2)

            result = await session.execute(
                select(Order)
                .where(
                    and_(
                        Order.status == OrderStatusEnum.delivered,
                        Order.delivered_at >= two_days_ago_from,
                        Order.delivered_at <= two_days_ago_to,
                    )
                )
            )

            recent_orders = result.scalars().all()

            notified = 0
            for order in recent_orders:
                try:
                    user_result = await session.execute(
                        select(User).where(User.id == order.user_id)
                    )
                    user = user_result.scalar_one_or_none()

                    product_result = await session.execute(
                        select(Product).where(Product.id == order.product_id)
                    )
                    product = product_result.scalar_one_or_none()

                    if not user or not product:
                        continue

                    # Персональные рекомендации на основе категории
                    recommendations = _get_recommendations(product.category.value)

                    if not recommendations:
                        continue

                    builder = InlineKeyboardBuilder()
                    builder.row(
                        InlineKeyboardButton(text="🛒 Смотреть", callback_data="catalog")
                    )

                    await bot.send_message(
                        user.telegram_id,
                        f"💡 **Рекомендуем к вашему {product.name}:**\n\n"
                        f"{recommendations}\n\n"
                        f"Все доступно в нашем каталоге!",
                        reply_markup=builder.as_markup(),
                        parse_mode="Markdown",
                    )
                    notified += 1

                except Exception as e:
                    logger.error(f"Failed to send recommendations to user {user.telegram_id}: {e}")

            logger.info(f"Recommendations job: notified {notified} users")

        await db_engine.dispose()

    except Exception as e:
        logger.error(f"Error in recommendations_job: {e}", exc_info=True)


def _get_recommendations(category: str) -> str:
    """Получить рекомендации на основе категории"""
    recommendations_map = {
        "gift_card": (
            "☁️ iCloud+ — для хранения фото и бэкапов\n"
            "🎵 Apple Music — подписка на музыку\n"
            "📺 Apple TV+ — сериалы и фильмы"
        ),
        "ai": (
            "🎨 Midjourney — генерация изображений\n"
            "💻 Cursor Pro — AI-редактор кода\n"
            "🔍 Perplexity Pro — AI поисковик"
        ),
        "streaming": (
            "🎬 Netflix — фильмы и сериалы\n"
            "🎵 Spotify Premium — музыка без рекламы\n"
            "▶️ YouTube Premium — без рекламы + Music"
        ),
        "icloud": (
            "🍎 Apple Gift Cards — пополнение баланса\n"
            "🎵 Apple Music Family — семейная подписка\n"
            "📺 Apple TV+ — эксклюзивный контент"
        ),
    }

    return recommendations_map.get(category, "")
