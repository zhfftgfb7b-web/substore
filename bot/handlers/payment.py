"""
Обработчики оплаты и покупки продуктов
"""
import logging
from datetime import datetime
from decimal import Decimal

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.inline import (
    get_back_to_menu_keyboard,
    get_payment_methods_keyboard,
)
from config import settings
from database import crud
from database.models import CategoryEnum, DeliveryTypeEnum, PaymentMethodEnum

logger = logging.getLogger(__name__)

router = Router(name="payment")


@router.callback_query(F.data.startswith("buy:"))
async def start_purchase(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
):
    """Начало покупки продукта"""
    try:
        product_id = int(callback.data.split(":")[1])
        user_id = callback.from_user.id

        # Получаем продукт
        product = await crud.get_product_by_id(session, product_id)
        if not product:
            await callback.answer("❌ Продукт не найден", show_alert=True)
            return

        # Проверяем наличие ключей для auto продуктов
        if product.delivery_type == DeliveryTypeEnum.auto:
            available = await crud.get_available_keys_count(session, product_id)
            if available == 0:
                await callback.answer("😔 Товар закончился", show_alert=True)
                return

        # Получаем пользователя
        user = await crud.get_user_by_telegram_id(session, user_id)
        if not user:
            await callback.answer("❌ Ошибка: пользователь не найден", show_alert=True)
            return

        # Применяем бонус если есть
        final_price = product.price
        bonus_used = 0
        if user.referral_bonus > 0:
            bonus_used = min(user.referral_bonus, int(product.price))
            final_price = product.price - Decimal(bonus_used)

        # Создаём заказ
        order = await crud.create_order(
            session=session,
            user_id=user.id,
            product_id=product_id,
            amount=final_price,
        )

        # Если использовали бонус - списываем
        if bonus_used > 0:
            await crud.update_user_bonus(session, user.id, -bonus_used)

        bonus_text = f"\n💰 Использовано бонусов: {bonus_used}₽" if bonus_used > 0 else ""

        await callback.message.edit_text(
            f"🛒 **Ваш заказ #{order.id}**\n\n"
            f"{product.emoji} {product.name}\n"
            f"💵 Сумма: {final_price}₽{bonus_text}\n\n"
            f"Выберите способ оплаты:",
            reply_markup=get_payment_methods_keyboard(order.id),
            parse_mode="Markdown"
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Error in start_purchase: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при создании заказа", show_alert=True)


@router.callback_query(F.data.startswith("pay:"))
async def process_payment_method(callback: CallbackQuery, session: AsyncSession):
    """Обработка выбора способа оплаты"""
    try:
        # Парсим: pay:method:order_id
        parts = callback.data.split(":")
        method = parts[1]
        order_id = int(parts[2])

        order = await crud.get_order_by_id(session, order_id)
        if not order:
            await callback.answer("❌ Заказ не найден", show_alert=True)
            return

        if method == "manual":
            await handle_manual_payment(callback, session, order)
        elif method == "stars":
            await handle_stars_payment(callback, session, order)
        elif method == "crypto":
            await handle_crypto_payment(callback, session, order)
        else:
            await callback.answer("❌ Неизвестный метод оплаты", show_alert=True)

    except Exception as e:
        logger.error(f"Error in process_payment_method: {e}", exc_info=True)
        await callback.answer("❌ Ошибка обработки платежа", show_alert=True)


async def handle_manual_payment(callback: CallbackQuery, session: AsyncSession, order):
    """Обработка ручного перевода на карту"""
    payment_id = f"manual_{order.id}_{int(datetime.utcnow().timestamp())}"
    await crud.update_order_payment(session, order.id, payment_id, PaymentMethodEnum.manual)

    # Отправляем реквизиты клиенту
    await callback.message.edit_text(
        f"💳 **Перевод на карту**\n\n"
        f"Заказ #{order.id}\n"
        f"💰 Сумма: {order.amount}₽\n\n"
        f"📋 **Реквизиты:**\n"
        f"Карта: `{settings.ADMIN_CARD_NUMBER}`\n"
        f"Получатель: {settings.ADMIN_CARD_OWNER}\n\n"
        f"После перевода нажмите кнопку ниже.\n"
        f"⏱ Проверка обычно занимает до 5 минут.",
        reply_markup=get_payment_confirmation_keyboard(payment_id="manual"),
        parse_mode="Markdown"
    )

    # Уведомляем админа о новом платеже
    try:
        from aiogram import Bot
        bot = callback.bot
        admin_id = settings.ADMIN_ID

        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton

        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"admin:confirm_payment:{order.id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin:decline_payment:{order.id}")
        )

        await bot.send_message(
            admin_id,
            f"💳 **Новый ручной платёж**\n\n"
            f"Заказ #{order.id}\n"
            f"👤 @{callback.from_user.username or 'noname'} (ID: {callback.from_user.id})\n"
            f"📦 {order.product.name}\n"
            f"💰 Сумма: {order.amount}₽\n\n"
            f"Проверьте поступление средств и подтвердите:",
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Failed to notify admin about manual payment: {e}")

    await callback.answer()


async def handle_stars_payment(callback: CallbackQuery, session: AsyncSession, order):
    """Обработка оплаты через Telegram Stars"""
    try:
        # Создаём invoice для Telegram Stars
        prices = [LabeledPrice(label=order.product.name, amount=int(order.amount))]

        payment_id = f"stars_{order.id}_{int(datetime.utcnow().timestamp())}"
        await crud.update_order_payment(session, order.id, payment_id, PaymentMethodEnum.stars)

        # Отправляем invoice
        await callback.message.answer_invoice(
            title=f"Заказ #{order.id}",
            description=f"{order.product.name}",
            payload=f"order_{order.id}",
            provider_token="",  # Для Stars не нужен
            currency="XTR",  # Telegram Stars
            prices=prices,
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Error in handle_stars_payment: {e}", exc_info=True)
        await callback.answer("❌ Ошибка создания invoice", show_alert=True)


async def handle_crypto_payment(callback: CallbackQuery, session: AsyncSession, order):
    """Обработка оплаты через CryptoPay"""
    # TODO: Интеграция с CryptoPay API
    # invoice_url = create_cryptopay_invoice(order.amount, order.id)

    payment_id = f"crypto_{order.id}_{int(datetime.utcnow().timestamp())}"
    await crud.update_order_payment(session, order.id, payment_id, PaymentMethodEnum.crypto)

    await callback.message.edit_text(
        f"₿ **Оплата криптой**\n\n"
        f"Заказ #{order.id}\n"
        f"Сумма: {order.amount}₽\n\n"
        f"⚠️ После оплаты нажмите кнопку 'Я оплатил'\n"
        f"Администратор проверит платёж и выдаст товар.",
        reply_markup=get_back_to_menu_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer(
        "ℹ️ Функция CryptoPay будет добавлена после настройки",
        show_alert=True
    )


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    """Обработчик pre-checkout для Telegram Stars"""
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment_handler(message: Message, session: AsyncSession):
    """Обработчик успешной оплаты через Telegram Stars"""
    try:
        # Парсим payload: order_{order_id}
        payload = message.successful_payment.invoice_payload
        order_id = int(payload.split("_")[1])

        order = await crud.get_order_by_id(session, order_id)
        if not order:
            logger.error(f"Order {order_id} not found after successful payment")
            return

        # Помечаем заказ как оплаченный
        await crud.mark_order_paid(session, order_id)

        # Обрабатываем выдачу товара
        await process_order_delivery(message, session, order)

    except Exception as e:
        logger.error(f"Error in successful_payment_handler: {e}", exc_info=True)
        await message.answer(
            "❌ Произошла ошибка после оплаты. Обратитесь в поддержку.",
            reply_markup=get_back_to_menu_keyboard()
        )


async def process_order_delivery(message: Message, session: AsyncSession, order):
    """Обработка выдачи товара после оплаты"""
    try:
        product = order.product
        bot = message.bot

        # Auto выдача - берём ключ из пула
        if product.delivery_type == DeliveryTypeEnum.auto:
            key = await crud.pop_available_key(session, product.id, order.user.id)

            if key:
                # Выдаём ключ
                await crud.deliver_order(session, order.id, key)

                # Создаём подписку
                await crud.create_subscription(
                    session=session,
                    user_id=order.user.id,
                    product_id=product.id,
                    order_id=order.id,
                    duration_days=product.duration_days,
                    apple_id_email=order.apple_id_email,
                )

                await message.answer(
                    f"✅ **Оплата успешна!**\n\n"
                    f"🎉 Ваш заказ #{order.id} выполнен\n\n"
                    f"🔑 **Ваш ключ:**\n"
                    f"`{key}`\n\n"
                    f"Спасибо за покупку!",
                    reply_markup=get_back_to_menu_keyboard(),
                    parse_mode="Markdown"
                )

                # Уведомляем админа об автоматической продаже
                from bot.utils.notifications import notify_admin_new_sale_auto
                await notify_admin_new_sale_auto(bot, order)

            else:
                # Ключи закончились - уведомляем клиента и админа
                await message.answer(
                    f"✅ Оплата прошла успешно!\n\n"
                    f"⏳ Ваш заказ #{order.id} передан администратору для выдачи.\n"
                    f"Ожидайте, товар будет выдан в течение 2 часов.",
                    reply_markup=get_back_to_menu_keyboard()
                )

                # Уведомляем админа о заказе без ключей (как manual)
                from bot.utils.notifications import notify_admin_new_sale_manual
                await notify_admin_new_sale_manual(bot, order)
                logger.warning(f"No keys available for auto product {product.id}, order {order.id}")

        # Manual выдача - уведомляем админа
        else:
            await message.answer(
                f"✅ Оплата прошла успешно!\n\n"
                f"⏳ Ваш заказ #{order.id} передан администратору.\n"
                f"Товар будет выдан в течение 2 часов.\n\n"
                f"Мы пришлём уведомление когда всё будет готово!",
                reply_markup=get_back_to_menu_keyboard()
            )

            # Уведомляем админа о ручном заказе
            from bot.utils.notifications import notify_admin_new_sale_manual
            await notify_admin_new_sale_manual(bot, order)
            logger.info(f"Manual order {order.id} paid, waiting for admin")

    except Exception as e:
        logger.error(f"Error in process_order_delivery: {e}", exc_info=True)
        await message.answer(
            "❌ Ошибка при выдаче товара. Обратитесь в поддержку.",
            reply_markup=get_back_to_menu_keyboard()
        )


@router.callback_query(F.data == "cancel_order")
async def cancel_order_handler(callback: CallbackQuery):
    """Отмена заказа"""
    await callback.message.edit_text(
        "❌ Заказ отменён",
        reply_markup=get_back_to_menu_keyboard()
    )
    await callback.answer()
