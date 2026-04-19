"""
Inline клавиатуры для Telegram бота
"""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.models import CategoryEnum, Order, Product


# ==================== MAIN MENU ====================

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню бота"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="🛒 Каталог", callback_data="catalog"),
        InlineKeyboardButton(text="📋 Мои заказы", callback_data="my_orders"),
    )
    builder.row(
        InlineKeyboardButton(text="👥 Реферальная программа", callback_data="referral"),
        InlineKeyboardButton(text="💬 Поддержка", callback_data="support"),
    )

    return builder.as_markup()


# ==================== CATALOG ====================

CATEGORY_EMOJI = {
    CategoryEnum.icloud: "☁️",
    CategoryEnum.vpn: "🔒",
    CategoryEnum.gift_card: "🎁",
    CategoryEnum.streaming: "🎵",
    CategoryEnum.ai: "🤖",
    CategoryEnum.other: "📦",
}

CATEGORY_NAMES = {
    CategoryEnum.icloud: "iCloud & Apple One",
    CategoryEnum.vpn: "VPN",
    CategoryEnum.gift_card: "Gift Cards",
    CategoryEnum.streaming: "Стриминг",
    CategoryEnum.ai: "AI сервисы",
    CategoryEnum.other: "Разное",
}


def get_categories_keyboard(categories: list[CategoryEnum]) -> InlineKeyboardMarkup:
    """Клавиатура выбора категории"""
    builder = InlineKeyboardBuilder()

    for category in categories:
        emoji = CATEGORY_EMOJI.get(category, "📦")
        name = CATEGORY_NAMES.get(category, category.value)
        builder.row(
            InlineKeyboardButton(
                text=f"{emoji} {name}",
                callback_data=f"category:{category.value}"
            )
        )

    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"))

    return builder.as_markup()


def get_products_keyboard(products: list[Product]) -> InlineKeyboardMarkup:
    """Клавиатура со списком продуктов в категории"""
    builder = InlineKeyboardBuilder()

    for product in products:
        builder.row(
            InlineKeyboardButton(
                text=f"{product.emoji} {product.name} — {product.price}₽",
                callback_data=f"product:{product.id}"
            )
        )

    builder.row(
        InlineKeyboardButton(text="◀️ Назад к категориям", callback_data="catalog")
    )

    return builder.as_markup()


def get_product_keyboard(product: Product, available_count: int = 0) -> InlineKeyboardMarkup:
    """Клавиатура карточки продукта"""
    builder = InlineKeyboardBuilder()

    # Кнопка "Купить" или "Нет в наличии"
    if product.delivery_type.value == "auto" and available_count == 0:
        builder.row(
            InlineKeyboardButton(text="❌ Нет в наличии", callback_data="out_of_stock")
        )
    else:
        builder.row(
            InlineKeyboardButton(text="💳 Купить", callback_data=f"buy:{product.id}")
        )

    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data=f"category:{product.category.value}")
    )

    return builder.as_markup()


# ==================== PAYMENT ====================

def get_payment_methods_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Клавиатура выбора способа оплаты"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="₿ Крипта (CryptoBot)", callback_data=f"pay:crypto:{order_id}")
    )
    builder.row(
        InlineKeyboardButton(text="💳 Перевод на карту", callback_data=f"pay:manual:{order_id}")
    )
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_order")
    )

    return builder.as_markup()


def get_payment_confirmation_keyboard(payment_url: str) -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения оплаты"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="💳 Оплатить", url=payment_url)
    )
    builder.row(
        InlineKeyboardButton(text="✅ Я оплатил", callback_data="payment_done")
    )
    builder.row(
        InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_order")
    )

    return builder.as_markup()


def get_apple_email_confirmation_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения Apple ID email"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="✅ Да, всё верно", callback_data=f"confirm_email:{order_id}")
    )
    builder.row(
        InlineKeyboardButton(text="✏️ Изменить email", callback_data=f"change_email:{order_id}")
    )
    builder.row(
        InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_order")
    )

    return builder.as_markup()


# ==================== ORDERS ====================

def get_order_status_keyboard(order: Order) -> InlineKeyboardMarkup:
    """Клавиатура для просмотра заказа"""
    builder = InlineKeyboardBuilder()

    if order.status.value == "delivered" and order.delivery_data:
        # Заказ доставлен, можно посмотреть данные
        builder.row(
            InlineKeyboardButton(text="📋 Показать данные", callback_data=f"show_order_data:{order.id}")
        )

    builder.row(
        InlineKeyboardButton(text="◀️ К моим заказам", callback_data="my_orders")
    )

    return builder.as_markup()


# ==================== REFERRAL ====================

def get_referral_keyboard(referral_link: str) -> InlineKeyboardMarkup:
    """Клавиатура реферальной программы"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="📤 Поделиться ссылкой", url=f"https://t.me/share/url?url={referral_link}")
    )
    builder.row(
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
    )

    return builder.as_markup()


# ==================== ADMIN ====================

def get_admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Админ меню в боте"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="📦 Заказы", callback_data="admin:orders"),
        InlineKeyboardButton(text="🔑 Добавить ключи", callback_data="admin:add_keys"),
    )
    builder.row(
        InlineKeyboardButton(text="📝 Продукты", callback_data="admin:products"),
        InlineKeyboardButton(text="👥 Пользователи", callback_data="admin:users"),
    )
    builder.row(
        InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats"),
        InlineKeyboardButton(text="📣 Рассылка", callback_data="admin:broadcast"),
    )

    return builder.as_markup()


def get_admin_products_keyboard(products: list[Product]) -> InlineKeyboardMarkup:
    """Клавиатура выбора продукта для добавления ключей"""
    builder = InlineKeyboardBuilder()

    for product in products:
        builder.row(
            InlineKeyboardButton(
                text=f"{product.emoji} {product.name}",
                callback_data=f"admin:select_product:{product.id}"
            )
        )

    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin:menu")
    )

    return builder.as_markup()


def get_admin_order_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для управления заказом"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="✅ Выполнен", callback_data=f"admin:complete:{order_id}"),
        InlineKeyboardButton(text="❌ Отменить", callback_data=f"admin:cancel:{order_id}"),
    )

    return builder.as_markup()


def get_broadcast_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения рассылки"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="✅ Отправить всем", callback_data="admin:broadcast_confirm")
    )
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin:menu")
    )

    return builder.as_markup()


# ==================== BACK TO MENU ====================

def get_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Простая кнопка возврата в главное меню"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"))
    return builder.as_markup()


# ==================== ADMIN PRODUCTS ====================

def get_manage_products_keyboard(products: list[Product]) -> InlineKeyboardMarkup:
    """Клавиатура управления продуктами"""
    builder = InlineKeyboardBuilder()

    for product in products:
        status_emoji = "✅" if product.is_active else "❌"
        builder.row(
            InlineKeyboardButton(
                text=f"{status_emoji} {product.emoji} {product.name} — {product.price}₽",
                callback_data=f"admin:manage_product:{product.id}"
            )
        )

    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="admin:menu")
    )

    return builder.as_markup()


def get_product_actions_keyboard(product_id: int, is_active: bool) -> InlineKeyboardMarkup:
    """Клавиатура действий над продуктом"""
    builder = InlineKeyboardBuilder()

    toggle_text = "❌ Выключить" if is_active else "✅ Включить"
    builder.row(
        InlineKeyboardButton(text=toggle_text, callback_data=f"admin:toggle_product:{product_id}")
    )
    builder.row(
        InlineKeyboardButton(text="💰 Изменить цену", callback_data=f"admin:change_price:{product_id}")
    )
    builder.row(
        InlineKeyboardButton(text="📋 История продаж", callback_data=f"admin:product_history:{product_id}")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="admin:products")
    )

    return builder.as_markup()


# ==================== ADMIN USERS ====================

def get_users_menu_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура меню управления пользователями"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="🔍 Найти пользователя", callback_data="admin:search_user")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="admin:menu")
    )

    return builder.as_markup()


def get_user_actions_keyboard(user_id: int, is_banned: bool) -> InlineKeyboardMarkup:
    """Клавиатура действий над пользователем"""
    builder = InlineKeyboardBuilder()

    ban_text = "✅ Разбанить" if is_banned else "🚫 Забанить"
    ban_callback = f"admin:unban_user:{user_id}" if is_banned else f"admin:ban_user:{user_id}"

    builder.row(
        InlineKeyboardButton(text=ban_text, callback_data=ban_callback)
    )
    builder.row(
        InlineKeyboardButton(text="📦 Заказы пользователя", callback_data=f"admin:user_orders:{user_id}")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад к поиску", callback_data="admin:users")
    )

    return builder.as_markup()


# ==================== WAITLIST ====================

def get_waitlist_keyboard(product_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для товара закончившегося (waitlist)"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="🔔 Уведомить меня", callback_data=f"waitlist:add:{product_id}")
    )
    builder.row(
        InlineKeyboardButton(text="⬅️ Другой продукт", callback_data="catalog")
    )

    return builder.as_markup()
