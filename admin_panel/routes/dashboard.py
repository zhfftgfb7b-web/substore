"""
Роут Dashboard админ-панели
"""
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from admin_panel.auth import verify_credentials
from database import crud
from database.engine import get_db_engine
from database.models import DeliveryTypeEnum

router = APIRouter()
templates = Jinja2Templates(directory="templates")


async def get_session():
    """Dependency для получения сессии БД"""
    db_engine = get_db_engine()
    async for session in db_engine.get_session():
        yield session


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    username: Annotated[str, Depends(verify_credentials)],
    session: AsyncSession = Depends(get_session),
):
    """Главная страница админ-панели"""
    # Статистика
    total_users = await crud.get_total_users(session)
    total_orders = await crud.get_total_orders(session)
    stats_today = await crud.get_stats_today(session)
    stats_month = await crud.get_stats_month(session)

    # Остаток ключей по продуктам
    products = await crud.get_all_products(session, active_only=False)
    key_stocks = []

    for product in products:
        if product.delivery_type == DeliveryTypeEnum.auto:
            stats = await crud.get_key_stats(session, product.id)
            key_stocks.append({
                "product": product,
                "available": stats["available"],
                "total": stats["total"],
                "used": stats["used"],
                "status": (
                    "success" if stats["available"] > 10
                    else "warning" if stats["available"] > 3
                    else "danger"
                ),
            })

    # Последние заказы
    recent_orders = await crud.get_orders_by_status(
        session, None, limit=10
    )  # Все статусы

    from database.models import OrderStatusEnum
    all_orders = []
    for status in OrderStatusEnum:
        orders = await crud.get_orders_by_status(session, status, limit=10)
        all_orders.extend(orders)

    # Сортируем по дате
    all_orders.sort(key=lambda x: x.created_at, reverse=True)
    recent_orders = all_orders[:10]

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "total_users": total_users,
            "total_orders": total_orders,
            "users_today": stats_today["users_today"],
            "orders_today": stats_today["orders_today"],
            "revenue_today": stats_today["revenue_today"],
            "revenue_month": stats_month["revenue_month"],
            "key_stocks": key_stocks,
            "recent_orders": recent_orders,
        },
    )
