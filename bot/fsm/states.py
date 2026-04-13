"""
FSM состояния для Telegram бота
"""
from aiogram.fsm.state import State, StatesGroup


class OrderStates(StatesGroup):
    """Состояния для оформления заказа"""
    waiting_apple_email = State()  # Ожидание ввода Apple ID email для iCloud заказа


class AdminStates(StatesGroup):
    """Состояния для админ-команд"""
    waiting_keys = State()  # Ожидание загрузки ключей в пул
    waiting_broadcast = State()  # Ожидание текста для рассылки
    selecting_product_for_keys = State()  # Выбор продукта для добавления ключей
