"""
FastAPI приложение для админ-панели SubStore
"""
import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from admin_panel.routes import dashboard, keys, orders, products, users
from config import settings
from database.engine import init_db

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Создание FastAPI приложения
app = FastAPI(
    title="SubStore Admin Panel",
    description="Админ-панель для управления магазином подписок",
    version="1.0.0",
)


@app.on_event("startup")
async def startup():
    """Инициализация при запуске"""
    logger.info("Starting admin panel...")

    # Инициализация БД
    init_db(settings.DATABASE_URL, echo=False)
    logger.info("Database initialized")


@app.on_event("shutdown")
async def shutdown():
    """Действия при остановке"""
    logger.info("Shutting down admin panel...")

    from database.engine import get_db_engine

    try:
        db_engine = get_db_engine()
        await db_engine.dispose()
        logger.info("Database connection closed")
    except Exception as e:
        logger.error(f"Error closing database: {e}")


# Подключение роутов
app.include_router(dashboard.router, prefix="/admin", tags=["Dashboard"])
app.include_router(orders.router, prefix="/admin/orders", tags=["Orders"])
app.include_router(products.router, prefix="/admin/products", tags=["Products"])
app.include_router(keys.router, prefix="/admin/keys", tags=["Keys"])
app.include_router(users.router, prefix="/admin/users", tags=["Users"])


@app.get("/")
async def root():
    """Редирект с корня на админ-панель"""
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="/admin")


@app.get("/health")
async def health():
    """Health check endpoint для Railway"""
    return {"status": "ok"}
