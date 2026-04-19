"""
Модели базы данных для SubStore
"""
import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Базовый класс для всех моделей"""
    pass


class CategoryEnum(enum.Enum):
    """Категории продуктов"""
    icloud = "icloud"
    vpn = "vpn"
    gift_card = "gift_card"
    streaming = "streaming"
    ai = "ai"
    other = "other"


class DeliveryTypeEnum(enum.Enum):
    """Типы доставки продукта"""
    auto = "auto"  # Автоматическая выдача из пула ключей
    manual = "manual"  # Ручная выдача администратором


class OrderStatusEnum(enum.Enum):
    """Статусы заказа"""
    pending = "pending"  # Ожидает оплаты
    paid = "paid"  # Оплачен, ожидает выдачи
    delivered = "delivered"  # Доставлен
    cancelled = "cancelled"  # Отменён


class PaymentMethodEnum(enum.Enum):
    """Методы оплаты"""
    manual = "manual"  # Ручной перевод на карту
    crypto = "crypto"  # CryptoBot
    stars = "stars"  # Telegram Stars


class User(Base):
    """Модель пользователя"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Реферальная система
    referral_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    referred_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    referral_bonus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # В рублях

    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    referrer: Mapped[Optional["User"]] = relationship(
        "User", remote_side=[id], back_populates="referrals"
    )
    referrals: Mapped[list["User"]] = relationship(
        "User", back_populates="referrer"
    )
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="user")
    subscriptions: Mapped[list["Subscription"]] = relationship("Subscription", back_populates="user")
    used_keys: Mapped[list["ProductKey"]] = relationship("ProductKey", back_populates="used_by_user")


class Product(Base):
    """Модель продукта"""
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[CategoryEnum] = mapped_column(Enum(CategoryEnum), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    cost_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)  # Себестоимость для расчёта маржи
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    delivery_type: Mapped[DeliveryTypeEnum] = mapped_column(Enum(DeliveryTypeEnum), nullable=False)
    emoji: Mapped[str] = mapped_column(String(10), nullable=False, default="📦")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    keys: Mapped[list["ProductKey"]] = relationship("ProductKey", back_populates="product")
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="product")
    subscriptions: Mapped[list["Subscription"]] = relationship("Subscription", back_populates="product")


class ProductKey(Base):
    """Модель ключа/кода продукта для автоматической выдачи"""
    __tablename__ = "product_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    key_value: Mapped[str] = mapped_column(Text, nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    used_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="keys")
    used_by_user: Mapped[Optional["User"]] = relationship("User", back_populates="used_keys")


class Order(Base):
    """Модель заказа"""
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[OrderStatusEnum] = mapped_column(
        Enum(OrderStatusEnum), default=OrderStatusEnum.pending, nullable=False, index=True
    )
    payment_method: Mapped[Optional[PaymentMethodEnum]] = mapped_column(Enum(PaymentMethodEnum), nullable=True)
    payment_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    delivery_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Выданный ключ или инструкция
    apple_id_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Для iCloud заказов
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False, index=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="orders")
    product: Mapped["Product"] = relationship("Product", back_populates="orders")
    subscription: Mapped[Optional["Subscription"]] = relationship(
        "Subscription", back_populates="order", uselist=False
    )


class Subscription(Base):
    """Модель активной подписки"""
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, unique=True)
    apple_id_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    renewal_reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="subscriptions")
    product: Mapped["Product"] = relationship("Product", back_populates="subscriptions")
    order: Mapped["Order"] = relationship("Order", back_populates="subscription")


class ProductWaitlist(Base):
    """Модель списка ожидания продукта (когда товар закончился)"""
    __tablename__ = "product_waitlist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    notified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User")
    product: Mapped["Product"] = relationship("Product")
