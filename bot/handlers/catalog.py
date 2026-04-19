"""
Обработчики каталога продуктов
"""
import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.inline import (
    CATEGORY_NAMES,
    get_categories_keyboard,
    get_product_keyboard,
    get_products_keyboard,
)
from database import crud
from database.models import CategoryEnum, DeliveryTypeEnum

logger = logging.getLogger(__name__)

router = Router(name="catalog")


@router.callback_query(F.data == "catalog")
async def show_catalog(callback: CallbackQuery, session: AsyncSession):
    """Показать каталог с категориями"""
    try:
        # Получаем список доступных категорий
        categories = await crud.get_available_categories(session)

        if not categories:
            await callback.message.edit_text(
                "😔 К сожалению, сейчас нет доступных товаров.\n"
                "Попробуйте позже!"
            )
            await callback.answer()
            return

        await callback.message.edit_text(
            "🛒 **Каталог**\n\n"
            "Выберите категорию:",
            reply_markup=get_categories_keyboard(categories),
            parse_mode="Markdown"
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Error in show_catalog: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при загрузке каталога", show_alert=True)


@router.callback_query(F.data.startswith("category:"))
async def show_category_products(callback: CallbackQuery, session: AsyncSession):
    """Показать продукты в категории"""
    try:
        # Парсим callback_data
        category_value = callback.data.split(":")[1]
        category = CategoryEnum(category_value)

        # Получаем продукты категории
        products = await crud.get_products_by_category(session, category, active_only=True)

        if not products:
            await callback.answer("В этой категории пока нет товаров", show_alert=True)
            return

        category_name = CATEGORY_NAMES.get(category, category.value)

        await callback.message.edit_text(
            f"**{category_name}**\n\n"
            f"Доступно товаров: {len(products)}",
            reply_markup=get_products_keyboard(products),
            parse_mode="Markdown"
        )
        await callback.answer()

    except ValueError:
        logger.error(f"Invalid category: {callback.data}")
        await callback.answer("❌ Неверная категория", show_alert=True)
    except Exception as e:
        logger.error(f"Error in show_category_products: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при загрузке продуктов", show_alert=True)


@router.callback_query(F.data.startswith("product:"))
async def show_product_card(callback: CallbackQuery, session: AsyncSession):
    """Показать карточку продукта"""
    try:
        # Парсим callback_data
        product_id = int(callback.data.split(":")[1])

        # Получаем продукт
        product = await crud.get_product_by_id(session, product_id)
        if not product:
            await callback.answer("❌ Продукт не найден", show_alert=True)
            return

        # Для auto продуктов - проверяем наличие ключей
        available_count = 0
        waitlist_count = 0
        availability_text = ""

        if product.delivery_type == DeliveryTypeEnum.auto:
            available_count = await crud.get_available_keys_count(session, product_id)
            if available_count > 0:
                availability_text = f"\n✅ В наличии: {available_count} шт."
            else:
                # Нет в наличии → показываем waitlist
                waitlist_count = await crud.get_waitlist_count_for_product(session, product_id)
                if waitlist_count > 0:
                    availability_text = f"\n⏳ Временно нет в наличии\n📋 {waitlist_count} чел. уже ждут"
                else:
                    availability_text = "\n⏳ Временно нет в наличии"
        else:
            availability_text = "\n⏱ Выдача до 2 часов"

        # Формируем карточку продукта
        card_text = (
            f"{product.emoji} **{product.name}**\n\n"
            f"{product.description}\n\n"
            f"💰 Цена: **{product.price}₽**\n"
            f"⏳ Срок: {product.duration_days} дней"
            f"{availability_text}"
        )

        await callback.message.edit_text(
            card_text,
            reply_markup=get_product_keyboard(product, available_count, waitlist_count),
            parse_mode="Markdown"
        )
        await callback.answer()

    except ValueError:
        logger.error(f"Invalid product_id in callback: {callback.data}")
        await callback.answer("❌ Неверный ID продукта", show_alert=True)
    except Exception as e:
        logger.error(f"Error in show_product_card: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при загрузке продукта", show_alert=True)
