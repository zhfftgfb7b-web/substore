"""
Обработчики команды /start, главное меню и поддержка
"""
import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.inline import get_back_to_menu_keyboard, get_main_menu_keyboard
from config import settings
from database import crud

logger = logging.getLogger(__name__)

router = Router(name="start")


WELCOME_TEXT = """👋 Добро пожаловать в SubStore!

Подписки и сервисы для России:
☁️ iCloud+ и Apple One
🔒 Приватное соединение
🎵 Spotify, YouTube Premium
🤖 ChatGPT, Midjourney
🎁 Gift Cards Apple и Steam

💳 Карта РФ, СБП, крипта, Telegram Stars
⚡️ Выдача от 5 минут"""


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession):
    """
    Обработчик команды /start
    Принимает deep link с реферальным кодом: /start REFERRAL_CODE
    """
    try:
        # Получаем telegram_id и данные пользователя
        telegram_id = message.from_user.id
        full_name = message.from_user.full_name
        username = message.from_user.username

        # Парсим аргументы команды (реферальный код)
        referred_by_code = None
        if message.text and len(message.text.split()) > 1:
            referred_by_code = message.text.split()[1]
            logger.info(f"User {telegram_id} came with referral code: {referred_by_code}")

        # Получаем или создаём пользователя
        user, is_new = await crud.get_or_create_user(
            session=session,
            telegram_id=telegram_id,
            full_name=full_name,
            username=username,
            referred_by_code=referred_by_code,
        )

        if is_new:
            logger.info(f"New user registered: {telegram_id} (@{username})")
            if referred_by_code:
                await message.answer(
                    "🎉 Добро пожаловать! Вы пришли по реферальной ссылке.\n"
                    "Ваш друг получил бонус 50₽!"
                )

        # Показываем приветственное сообщение
        await message.answer(
            WELCOME_TEXT,
            reply_markup=get_main_menu_keyboard()
        )

    except Exception as e:
        logger.error(f"Error in cmd_start: {e}", exc_info=True)
        await message.answer(
            "❌ Произошла ошибка при запуске бота. Попробуйте позже.",
            reply_markup=get_back_to_menu_keyboard()
        )


@router.callback_query(F.data == "main_menu")
async def show_main_menu(callback: CallbackQuery):
    """Показать главное меню"""
    try:
        await callback.message.edit_text(
            WELCOME_TEXT,
            reply_markup=get_main_menu_keyboard()
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Error in show_main_menu: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data == "support")
async def show_support(callback: CallbackQuery):
    """Показать информацию о поддержке"""
    try:
        support_text = (
            f"💬 **Поддержка SubStore**\n\n"
            f"По всем вопросам обращайтесь: @{settings.SUPPORT_USERNAME}\n\n"
            f"Мы ответим в течение 2 часов!"
        )

        await callback.message.edit_text(
            support_text,
            reply_markup=get_back_to_menu_keyboard(),
            parse_mode="Markdown"
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Error in show_support: {e}", exc_info=True)
        await callback.answer("❌ Ошибка", show_alert=True)


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    help_text = (
        "📖 **Помощь SubStore**\n\n"
        "🛒 **Каталог** — выбрать и купить подписку\n"
        "📋 **Мои заказы** — история покупок\n"
        "👥 **Реферальная программа** — приглашай друзей и получай бонусы\n"
        "💬 **Поддержка** — связаться с нами\n\n"
        f"По вопросам: @{settings.SUPPORT_USERNAME}"
    )

    await message.answer(
        help_text,
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown"
    )
