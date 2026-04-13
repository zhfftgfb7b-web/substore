"""
Роут Orders админ-панели
"""
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from admin_panel.auth import verify_credentials
from admin_panel.routes.dashboard import get_session
from database import crud
from database.models import OrderStatusEnum

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def orders_page(
    request: Request,
    username: Annotated[str, Depends(verify_credentials)],
    session: AsyncSession = Depends(get_session),
    status: str = None,
):
    """Страница управления заказами"""
    # Получаем заказы
    if status:
        try:
            status_enum = OrderStatusEnum(status)
            orders = await crud.get_orders_by_status(session, status_enum, limit=100)
        except ValueError:
            orders = []
    else:
        # Все заказы
        all_orders = []
        for st in OrderStatusEnum:
            orders_list = await crud.get_orders_by_status(session, st, limit=100)
            all_orders.extend(orders_list)

        # Сортируем по дате
        all_orders.sort(key=lambda x: x.created_at, reverse=True)
        orders = all_orders[:100]

    return templates.TemplateResponse(
        "orders.html",
        {
            "request": request,
            "orders": orders,
            "current_status": status,
            "statuses": [s.value for s in OrderStatusEnum],
        },
    )


@router.post("/{order_id}/complete")
async def complete_order(
    order_id: int,
    username: Annotated[str, Depends(verify_credentials)],
    session: AsyncSession = Depends(get_session),
    delivery_data: str = Form(...),
):
    """Пометить заказ как выполненный"""
    await crud.deliver_order(session, order_id, delivery_data)

    # Создать подписку
    order = await crud.get_order_by_id(session, order_id)
    if order:
        await crud.create_subscription(
            session=session,
            user_id=order.user.id,
            product_id=order.product.id,
            order_id=order.id,
            duration_days=order.product.duration_days,
            apple_id_email=order.apple_id_email,
        )

    return RedirectResponse(url="/admin/orders", status_code=303)


@router.post("/{order_id}/cancel")
async def cancel_order(
    order_id: int,
    username: Annotated[str, Depends(verify_credentials)],
    session: AsyncSession = Depends(get_session),
):
    """Отменить заказ"""
    await crud.cancel_order(session, order_id)
    return RedirectResponse(url="/admin/orders", status_code=303)
