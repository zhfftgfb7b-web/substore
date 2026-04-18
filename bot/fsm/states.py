"""
FSM состояния для Telegram бота
"""
from aiogram.fsm.state import State, StatesGroup


class OrderStates(StatesGroup):
    """Состояния для оформления заказа"""
    # NOTE: iCloud Family subscriptions removed from MVP
    # Will be added in v3 when we have manual setup process


class AdminStates(StatesGroup):
    """Состояния для админ-команд"""
    waiting_keys = State()  # Ожидание загрузки ключей в пул
    waiting_broadcast = State()  # Ожидание текста для рассылки
    selecting_product_for_keys = State()  # Выбор продукта для добавления ключей
    waiting_new_price = State()  # Ожидание новой цены для продукта
    waiting_user_search = State()  # Ожидание поискового запроса пользователя
