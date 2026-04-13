"""
Точка входа Telegram бота SubStore
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from redis.asyncio import Redis

from bot.handlers import admin, catalog, payment, profile, start
from bot.middlewares.db import DatabaseMiddleware
from config import settings
from database import crud
from database.engine import init_db

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def set_bot_commands(bot: Bot):
    """Установить команды бота"""
    commands = [
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="help", description="Помощь"),
        BotCommand(command="admin", description="Админ-панель"),
    ]
    await bot.set_my_commands(commands)


async def check_low_stock_task():
    """Фоновая задача: проверка малого запаса ключей"""
    try:
        from database.engine import get_db_engine

        db_engine = get_db_engine()

        async for session in db_engine.get_session():
            # Получаем продукты с малым запасом
            low_stock_products = await crud.get_low_stock_products(session, threshold=3)

            if low_stock_products:
                # TODO: Уведомить админа через бот
                logger.warning(
                    f"Low stock alert: {len(low_stock_products)} products have less than 3 keys"
                )
                for product, available in low_stock_products:
                    logger.warning(f"  - {product.name}: {available} keys")

    except Exception as e:
        logger.error(f"Error in check_low_stock_task: {e}", exc_info=True)


async def send_renewal_reminders_task(bot: Bot):
    """Фоновая задача: отправка напоминаний о продлении подписок"""
    try:
        from database.engine import get_db_engine

        db_engine = get_db_engine()

        async for session in db_engine.get_session():
            # Получаем подписки истекающие через 3 дня
            expiring_subs = await crud.get_expiring_subscriptions(session, days_before=3)

            for sub in expiring_subs:
                try:
                    # Отправляем напоминание
                    expires_date = sub.expires_at.strftime("%d.%m.%Y")

                    await bot.send_message(
                        sub.user.telegram_id,
                        f"⏰ **Напоминание о продлении**\n\n"
                        f"Ваша подписка {sub.product.emoji} {sub.product.name} "
                        f"истекает {expires_date}.\n\n"
                        f"Не забудьте продлить её в каталоге!",
                        parse_mode="Markdown",
                    )

                    # Помечаем что напоминание отправлено
                    await crud.mark_reminder_sent(session, sub.id)

                    logger.info(f"Sent renewal reminder for subscription {sub.id}")

                except Exception as e:
                    logger.error(
                        f"Failed to send reminder to user {sub.user.telegram_id}: {e}"
                    )

    except Exception as e:
        logger.error(f"Error in send_renewal_reminders_task: {e}", exc_info=True)


async def yookassa_webhook_handler(request: web.Request) -> web.Response:
    """Обработчик webhook от ЮКассы"""
    try:
        data = await request.json()
        logger.info(f"Received YooKassa webhook: {data}")

        # TODO: Обработка webhook от ЮКассы
        # 1. Проверить подпись запроса
        # 2. Получить payment_id из data
        # 3. Найти заказ по payment_id
        # 4. Пометить как оплаченный
        # 5. Выдать товар

        return web.json_response({"status": "ok"})

    except Exception as e:
        logger.error(f"Error in yookassa_webhook_handler: {e}", exc_info=True)
        return web.json_response({"status": "error"}, status=500)


async def on_startup(bot: Bot, dispatcher: Dispatcher):
    """Действия при запуске бота"""
    logger.info("Bot starting...")

    # Инициализация БД
    init_db(settings.DATABASE_URL, echo=False)
    logger.info("Database initialized")

    # Устанавливаем команды
    await set_bot_commands(bot)

    # Запускаем scheduler для фоновых задач
    scheduler = AsyncIOScheduler(timezone="UTC")

    # Каждый час - проверка запасов ключей
    scheduler.add_job(
        check_low_stock_task,
        trigger="cron",
        hour="*",  # Каждый час
        minute=0,
    )

    # Каждый день в 10:00 UTC - напоминания о продлении
    scheduler.add_job(
        send_renewal_reminders_task,
        trigger="cron",
        hour=10,
        minute=0,
        args=[bot],
    )

    scheduler.start()
    logger.info("Scheduler started")

    # Сохраняем scheduler в dispatcher для доступа
    dispatcher["scheduler"] = scheduler

    logger.info("Bot started successfully")


async def on_shutdown(bot: Bot, dispatcher: Dispatcher):
    """Действия при остановке бота"""
    logger.info("Bot shutting down...")

    # Останавливаем scheduler
    if "scheduler" in dispatcher.workflow_data:
        scheduler = dispatcher["scheduler"]
        scheduler.shutdown()
        logger.info("Scheduler stopped")

    # Закрываем соединение с БД
    from database.engine import get_db_engine

    try:
        db_engine = get_db_engine()
        await db_engine.dispose()
        logger.info("Database connection closed")
    except Exception as e:
        logger.error(f"Error closing database: {e}")

    logger.info("Bot stopped")


async def main():
    """Главная функция"""
    # Инициализация Redis для FSM
    redis = Redis.from_url(settings.REDIS_URL)
    storage = RedisStorage(redis)

    # Инициализация бота
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Инициализация диспетчера
    dp = Dispatcher(storage=storage)

    # Регистрация middlewares
    dp.update.middleware(DatabaseMiddleware())

    # Регистрация роутеров
    dp.include_router(start.router)
    dp.include_router(catalog.router)
    dp.include_router(payment.router)
    dp.include_router(profile.router)
    dp.include_router(admin.router)

    # Регистрация startup/shutdown
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Создаём aiohttp app для webhook
    app = web.Application()

    # Добавляем webhook endpoint для ЮКассы
    app.router.add_post("/webhook/yookassa", yookassa_webhook_handler)

    # Настраиваем webhook handler для Telegram
    webhook_path = "/webhook/telegram"
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=webhook_path)

    # Настраиваем startup/shutdown для aiohttp
    setup_application(app, dp, bot=bot)

    # Запускаем бота
    # На Railway используется webhook через aiohttp
    # Локально можно использовать polling: await dp.start_polling(bot)

    try:
        # Webhook режим (для production на Railway)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host="0.0.0.0", port=8080)
        await site.start()

        logger.info("Webhook server started on http://0.0.0.0:8080")
        logger.info(f"Webhook URL: /webhook/telegram")

        # Держим приложение запущенным
        await asyncio.Event().wait()

    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        await bot.session.close()
        await redis.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
