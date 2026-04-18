"""
CRUD операции для работы с базой данных
"""
import logging
import secrets
import string
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import (
    CategoryEnum,
    DeliveryTypeEnum,
    Order,
    OrderStatusEnum,
    PaymentMethodEnum,
    Product,
    ProductKey,
    Subscription,
    User,
)

logger = logging.getLogger(__name__)


# ==================== USER CRUD ====================

def generate_referral_code(length: int = 8) -> str:
    """Сгенерировать уникальный реферальный код"""
    chars = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> Optional[User]:
    """Получить пользователя по telegram_id"""
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


async def get_user_by_referral_code(session: AsyncSession, referral_code: str) -> Optional[User]:
    """Получить пользователя по реферальному коду"""
    result = await session.execute(
        select(User).where(User.referral_code == referral_code)
    )
    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    telegram_id: int,
    full_name: str,
    username: Optional[str] = None,
    referred_by_code: Optional[str] = None,
) -> User:
    """
    Создать нового пользователя

    Args:
        session: Сессия БД
        telegram_id: Telegram ID пользователя
        full_name: Полное имя пользователя
        username: Username в Telegram (опционально)
        referred_by_code: Реферальный код пригласившего (опционально)

    Returns:
        User: Созданный пользователь
    """
    # Генерируем уникальный реферальный код
    while True:
        ref_code = generate_referral_code()
        existing = await get_user_by_referral_code(session, ref_code)
        if not existing:
            break

    # Ищем реферера
    referrer_id = None
    if referred_by_code:
        referrer = await get_user_by_referral_code(session, referred_by_code)
        if referrer:
            referrer_id = referrer.id
            # Начисляем бонус рефереру
            referrer.referral_bonus += 50
            logger.info(f"Referral bonus +50 RUB to user {referrer.telegram_id}")

    user = User(
        telegram_id=telegram_id,
        username=username,
        full_name=full_name,
        referral_code=ref_code,
        referred_by=referrer_id,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    logger.info(f"Created user {telegram_id} with referral code {ref_code}")
    return user


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    full_name: str,
    username: Optional[str] = None,
    referred_by_code: Optional[str] = None,
) -> tuple[User, bool]:
    """
    Получить существующего или создать нового пользователя

    Returns:
        Tuple[User, bool]: (пользователь, создан ли новый)
    """
    user = await get_user_by_telegram_id(session, telegram_id)
    if user:
        return user, False

    user = await create_user(session, telegram_id, full_name, username, referred_by_code)
    return user, True


async def get_user_referrals_count(session: AsyncSession, user_id: int) -> int:
    """Получить количество рефералов пользователя"""
    result = await session.execute(
        select(func.count()).where(User.referred_by == user_id)
    )
    return result.scalar() or 0


async def update_user_bonus(session: AsyncSession, user_id: int, bonus_change: int) -> None:
    """Изменить бонусный баланс пользователя"""
    user = await session.get(User, user_id)
    if user:
        user.referral_bonus += bonus_change
        await session.commit()


async def ban_user(session: AsyncSession, user_id: int, banned: bool = True) -> None:
    """Заблокировать/разблокировать пользователя"""
    user = await session.get(User, user_id)
    if user:
        user.is_banned = banned
        await session.commit()
        logger.info(f"User {user.telegram_id} {'banned' if banned else 'unbanned'}")


async def get_all_active_users(session: AsyncSession) -> list[User]:
    """Получить всех незаблокированных пользователей (для рассылки)"""
    result = await session.execute(
        select(User).where(User.is_banned == False)
    )
    return list(result.scalars().all())


# ==================== PRODUCT CRUD ====================

async def get_product_by_id(session: AsyncSession, product_id: int) -> Optional[Product]:
    """Получить продукт по ID"""
    return await session.get(Product, product_id)


async def get_all_products(session: AsyncSession, active_only: bool = True) -> list[Product]:
    """Получить все продукты"""
    query = select(Product).order_by(Product.sort_order, Product.id)
    if active_only:
        query = query.where(Product.is_active == True)

    result = await session.execute(query)
    return list(result.scalars().all())


async def get_products_by_category(
    session: AsyncSession, category: CategoryEnum, active_only: bool = True
) -> list[Product]:
    """Получить продукты по категории"""
    query = select(Product).where(Product.category == category).order_by(Product.sort_order, Product.id)
    if active_only:
        query = query.where(Product.is_active == True)

    result = await session.execute(query)
    return list(result.scalars().all())


async def get_available_categories(session: AsyncSession) -> list[CategoryEnum]:
    """Получить список категорий с активными продуктами"""
    result = await session.execute(
        select(Product.category)
        .where(Product.is_active == True)
        .distinct()
        .order_by(Product.category)
    )
    return list(result.scalars().all())


async def update_product_price(session: AsyncSession, product_id: int, new_price: Decimal) -> None:
    """Обновить цену продукта"""
    product = await session.get(Product, product_id)
    if product:
        product.price = new_price
        await session.commit()
        logger.info(f"Updated product {product_id} price to {new_price}")


async def toggle_product_active(session: AsyncSession, product_id: int) -> bool:
    """Включить/выключить продукт, возвращает новый статус"""
    product = await session.get(Product, product_id)
    if product:
        product.is_active = not product.is_active
        await session.commit()
        logger.info(f"Product {product_id} is_active set to {product.is_active}")
        return product.is_active
    return False


# ==================== PRODUCT KEY CRUD ====================

async def get_available_keys_count(session: AsyncSession, product_id: int) -> int:
    """Получить количество свободных ключей для продукта"""
    result = await session.execute(
        select(func.count())
        .where(and_(ProductKey.product_id == product_id, ProductKey.is_used == False))
    )
    return result.scalar() or 0


async def get_key_stats(session: AsyncSession, product_id: int) -> dict:
    """Получить статистику ключей для продукта"""
    total = await session.execute(
        select(func.count()).where(ProductKey.product_id == product_id)
    )
    used = await session.execute(
        select(func.count())
        .where(and_(ProductKey.product_id == product_id, ProductKey.is_used == True))
    )
    total_count = total.scalar() or 0
    used_count = used.scalar() or 0

    return {
        "total": total_count,
        "used": used_count,
        "available": total_count - used_count,
    }


async def pop_available_key(
    session: AsyncSession, product_id: int, user_id: int
) -> Optional[str]:
    """
    Получить и пометить как использованный свободный ключ для продукта

    Returns:
        Optional[str]: Значение ключа или None если ключей нет
    """
    result = await session.execute(
        select(ProductKey)
        .where(and_(ProductKey.product_id == product_id, ProductKey.is_used == False))
        .limit(1)
        .with_for_update(skip_locked=True)  # Блокировка для предотвращения race condition
    )
    key = result.scalar_one_or_none()

    if key:
        key.is_used = True
        key.used_by = user_id
        key.used_at = datetime.utcnow()
        await session.commit()
        logger.info(f"Key {key.id} for product {product_id} used by user {user_id}")
        return key.key_value

    logger.warning(f"No available keys for product {product_id}")
    return None


async def add_keys_to_pool(
    session: AsyncSession, product_id: int, keys: list[str]
) -> int:
    """
    Добавить ключи в пул

    Returns:
        int: Количество добавленных ключей
    """
    for key_value in keys:
        key = ProductKey(product_id=product_id, key_value=key_value.strip())
        session.add(key)

    await session.commit()
    logger.info(f"Added {len(keys)} keys to product {product_id}")
    return len(keys)


async def get_low_stock_products(session: AsyncSession, threshold: int = 3) -> list[tuple[Product, int]]:
    """Получить продукты с малым запасом ключей (для уведомлений админа)"""
    # Подзапрос для подсчёта доступных ключей
    subquery = (
        select(ProductKey.product_id, func.count().label("available"))
        .where(ProductKey.is_used == False)
        .group_by(ProductKey.product_id)
        .subquery()
    )

    # Основной запрос: продукты с auto выдачей и малым запасом
    result = await session.execute(
        select(Product, subquery.c.available)
        .outerjoin(subquery, Product.id == subquery.c.product_id)
        .where(
            and_(
                Product.is_active == True,
                Product.delivery_type == DeliveryTypeEnum.auto,
                or_(
                    subquery.c.available == None,
                    subquery.c.available < threshold
                )
            )
        )
    )

    products_with_stock = []
    for product, available in result.all():
        products_with_stock.append((product, available or 0))

    return products_with_stock


# ==================== ORDER CRUD ====================

async def create_order(
    session: AsyncSession,
    user_id: int,
    product_id: int,
    amount: Decimal,
    apple_id_email: Optional[str] = None,
) -> Order:
    """Создать новый заказ"""
    order = Order(
        user_id=user_id,
        product_id=product_id,
        amount=amount,
        status=OrderStatusEnum.pending,
        apple_id_email=apple_id_email,
    )
    session.add(order)
    await session.commit()
    await session.refresh(order)

    logger.info(f"Created order {order.id} for user {user_id}, product {product_id}")
    return order


async def get_order_by_id(session: AsyncSession, order_id: int) -> Optional[Order]:
    """Получить заказ по ID с загрузкой связанных данных"""
    result = await session.execute(
        select(Order)
        .options(selectinload(Order.user), selectinload(Order.product))
        .where(Order.id == order_id)
    )
    return result.scalar_one_or_none()


async def get_order_by_payment_id(session: AsyncSession, payment_id: str) -> Optional[Order]:
    """Получить заказ по ID платежа (для webhook)"""
    result = await session.execute(
        select(Order)
        .options(selectinload(Order.user), selectinload(Order.product))
        .where(Order.payment_id == payment_id)
    )
    return result.scalar_one_or_none()


async def update_order_payment(
    session: AsyncSession,
    order_id: int,
    payment_id: str,
    payment_method: PaymentMethodEnum,
) -> None:
    """Обновить платёжные данные заказа"""
    order = await session.get(Order, order_id)
    if order:
        order.payment_id = payment_id
        order.payment_method = payment_method
        await session.commit()


async def mark_order_paid(session: AsyncSession, order_id: int) -> None:
    """Пометить заказ как оплаченный"""
    order = await session.get(Order, order_id)
    if order:
        order.status = OrderStatusEnum.paid
        await session.commit()
        logger.info(f"Order {order_id} marked as paid")


async def deliver_order(
    session: AsyncSession, order_id: int, delivery_data: str
) -> None:
    """Пометить заказ как доставленный"""
    order = await session.get(Order, order_id)
    if order:
        order.status = OrderStatusEnum.delivered
        order.delivery_data = delivery_data
        order.delivered_at = datetime.utcnow()
        await session.commit()
        logger.info(f"Order {order_id} delivered")


async def cancel_order(session: AsyncSession, order_id: int) -> None:
    """Отменить заказ"""
    order = await session.get(Order, order_id)
    if order:
        order.status = OrderStatusEnum.cancelled
        await session.commit()
        logger.info(f"Order {order_id} cancelled")


async def get_user_orders(
    session: AsyncSession, user_id: int, limit: int = 10
) -> list[Order]:
    """Получить заказы пользователя"""
    result = await session.execute(
        select(Order)
        .options(selectinload(Order.product))
        .where(Order.user_id == user_id)
        .order_by(Order.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_pending_manual_orders(session: AsyncSession) -> list[Order]:
    """Получить заказы требующие ручной обработки"""
    result = await session.execute(
        select(Order)
        .join(Product)
        .options(selectinload(Order.user), selectinload(Order.product))
        .where(
            and_(
                Order.status == OrderStatusEnum.paid,
                Product.delivery_type == DeliveryTypeEnum.manual,
            )
        )
        .order_by(Order.created_at.asc())
    )
    return list(result.scalars().all())


async def get_orders_by_status(
    session: AsyncSession,
    status: OrderStatusEnum,
    limit: Optional[int] = None,
) -> list[Order]:
    """Получить заказы по статусу"""
    query = (
        select(Order)
        .options(selectinload(Order.user), selectinload(Order.product))
        .where(Order.status == status)
        .order_by(Order.created_at.desc())
    )

    if limit:
        query = query.limit(limit)

    result = await session.execute(query)
    return list(result.scalars().all())


# ==================== SUBSCRIPTION CRUD ====================

async def create_subscription(
    session: AsyncSession,
    user_id: int,
    product_id: int,
    order_id: int,
    duration_days: int,
    apple_id_email: Optional[str] = None,
) -> Subscription:
    """Создать подписку"""
    expires_at = datetime.utcnow() + timedelta(days=duration_days)

    subscription = Subscription(
        user_id=user_id,
        product_id=product_id,
        order_id=order_id,
        apple_id_email=apple_id_email,
        expires_at=expires_at,
    )
    session.add(subscription)
    await session.commit()
    await session.refresh(subscription)

    logger.info(f"Created subscription {subscription.id} for user {user_id}, expires {expires_at}")
    return subscription


async def get_user_subscriptions(
    session: AsyncSession, user_id: int, active_only: bool = True
) -> list[Subscription]:
    """Получить подписки пользователя"""
    query = (
        select(Subscription)
        .options(selectinload(Subscription.product))
        .where(Subscription.user_id == user_id)
        .order_by(Subscription.created_at.desc())
    )

    if active_only:
        query = query.where(Subscription.is_active == True)

    result = await session.execute(query)
    return list(result.scalars().all())


async def get_expiring_subscriptions(
    session: AsyncSession, days_before: int = 3
) -> list[Subscription]:
    """Получить подписки истекающие в ближайшие N дней (для напоминаний)"""
    now = datetime.utcnow()
    threshold = now + timedelta(days=days_before)

    result = await session.execute(
        select(Subscription)
        .options(selectinload(Subscription.user), selectinload(Subscription.product))
        .where(
            and_(
                Subscription.is_active == True,
                Subscription.renewal_reminder_sent == False,
                Subscription.expires_at <= threshold,
                Subscription.expires_at > now,
            )
        )
    )
    return list(result.scalars().all())


async def mark_reminder_sent(session: AsyncSession, subscription_id: int) -> None:
    """Пометить что напоминание о продлении отправлено"""
    subscription = await session.get(Subscription, subscription_id)
    if subscription:
        subscription.renewal_reminder_sent = True
        await session.commit()


async def deactivate_subscription(session: AsyncSession, subscription_id: int) -> None:
    """Деактивировать подписку"""
    subscription = await session.get(Subscription, subscription_id)
    if subscription:
        subscription.is_active = False
        await session.commit()
        logger.info(f"Subscription {subscription_id} deactivated")


# ==================== STATISTICS ====================

async def get_stats_today(session: AsyncSession) -> dict:
    """Получить статистику за сегодня"""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    # Новых пользователей
    users_today = await session.execute(
        select(func.count()).where(User.created_at >= today_start)
    )

    # Заказов сегодня
    orders_today = await session.execute(
        select(func.count()).where(Order.created_at >= today_start)
    )

    # Выручка сегодня
    revenue_today = await session.execute(
        select(func.coalesce(func.sum(Order.amount), 0))
        .where(
            and_(
                Order.created_at >= today_start,
                Order.status.in_([OrderStatusEnum.paid, OrderStatusEnum.delivered])
            )
        )
    )

    return {
        "users_today": users_today.scalar() or 0,
        "orders_today": orders_today.scalar() or 0,
        "revenue_today": float(revenue_today.scalar() or 0),
    }


async def get_stats_month(session: AsyncSession) -> dict:
    """Получить статистику за текущий месяц"""
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    revenue_month = await session.execute(
        select(func.coalesce(func.sum(Order.amount), 0))
        .where(
            and_(
                Order.created_at >= month_start,
                Order.status.in_([OrderStatusEnum.paid, OrderStatusEnum.delivered])
            )
        )
    )

    return {
        "revenue_month": float(revenue_month.scalar() or 0),
    }


async def get_total_users(session: AsyncSession) -> int:
    """Получить общее количество пользователей"""
    result = await session.execute(select(func.count()).select_from(User))
    return result.scalar() or 0


async def get_total_orders(session: AsyncSession) -> int:
    """Получить общее количество заказов"""
    result = await session.execute(select(func.count()).select_from(Order))
    return result.scalar() or 0


async def search_users(
    session: AsyncSession, search_term: str, limit: int = 50
) -> list[User]:
    """Поиск пользователей по username или telegram_id"""
    # Пытаемся преобразовать в число для поиска по telegram_id
    try:
        tid = int(search_term)
        result = await session.execute(
            select(User).where(User.telegram_id == tid)
        )
        user = result.scalar_one_or_none()
        return [user] if user else []
    except ValueError:
        pass

    # Поиск по username
    result = await session.execute(
        select(User)
        .where(User.username.ilike(f"%{search_term}%"))
        .limit(limit)
    )
    return list(result.scalars().all())


# ==================== PRODUCT STATISTICS ====================

async def get_product_stats(session: AsyncSession, product_id: int) -> dict:
    """
    Получить детальную статистику по продукту

    Returns:
        dict: {
            "total_sold": int,  # Всего продано
            "revenue": Decimal,  # Общая выручка
            "margin": Decimal,  # Общая маржа (если есть cost_price)
        }
    """
    product = await session.get(Product, product_id)
    if not product:
        return {"total_sold": 0, "revenue": Decimal(0), "margin": Decimal(0)}

    # Подсчёт продаж (delivered заказы)
    result = await session.execute(
        select(func.count(), func.coalesce(func.sum(Order.amount), 0))
        .where(
            and_(
                Order.product_id == product_id,
                Order.status == OrderStatusEnum.delivered
            )
        )
    )
    total_sold, revenue = result.one()

    # Рассчитываем маржу если есть cost_price
    margin = Decimal(0)
    if product.cost_price and total_sold > 0:
        margin = (product.price - product.cost_price) * total_sold

    return {
        "total_sold": total_sold or 0,
        "revenue": Decimal(revenue or 0),
        "margin": margin,
    }


async def get_product_sales_history(
    session: AsyncSession, product_id: int, limit: int = 20
) -> list[Order]:
    """Получить историю продаж продукта"""
    result = await session.execute(
        select(Order)
        .options(selectinload(Order.user))
        .where(
            and_(
                Order.product_id == product_id,
                Order.status == OrderStatusEnum.delivered
            )
        )
        .order_by(Order.delivered_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_top_products(session: AsyncSession, limit: int = 5) -> list[tuple[Product, int, Decimal]]:
    """
    Получить топ-продукты по количеству продаж

    Returns:
        list[tuple[Product, int, Decimal]]: список (продукт, кол-во продаж, выручка)
    """
    result = await session.execute(
        select(
            Product,
            func.count(Order.id).label("sales_count"),
            func.coalesce(func.sum(Order.amount), 0).label("revenue")
        )
        .join(Order, Order.product_id == Product.id)
        .where(Order.status == OrderStatusEnum.delivered)
        .group_by(Product.id)
        .order_by(func.count(Order.id).desc())
        .limit(limit)
    )

    return [(row[0], row[1], Decimal(row[2])) for row in result.all()]


async def get_payment_methods_breakdown(session: AsyncSession) -> dict[str, dict]:
    """
    Получить разбивку по способам оплаты

    Returns:
        dict: {
            "crypto": {"count": 10, "revenue": 50000},
            "manual": {"count": 5, "revenue": 25000},
            ...
        }
    """
    result = await session.execute(
        select(
            Order.payment_method,
            func.count(Order.id).label("count"),
            func.coalesce(func.sum(Order.amount), 0).label("revenue")
        )
        .where(Order.status.in_([OrderStatusEnum.paid, OrderStatusEnum.delivered]))
        .group_by(Order.payment_method)
    )

    breakdown = {}
    for row in result.all():
        if row[0]:  # payment_method не None
            method = row[0].value
            breakdown[method] = {
                "count": row[1] or 0,
                "revenue": Decimal(row[2] or 0)
            }

    return breakdown
