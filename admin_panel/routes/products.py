"""
Роут Products админ-панели
"""
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from admin_panel.auth import verify_credentials
from admin_panel.routes.dashboard import get_session
from database import crud

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def products_page(
    request: Request,
    username: Annotated[str, Depends(verify_credentials)],
    session: AsyncSession = Depends(get_session),
):
    """Страница управления продуктами"""
    products = await crud.get_all_products(session, active_only=False)

    return templates.TemplateResponse(
        "products.html",
        {
            "request": request,
            "products": products,
        },
    )


@router.post("/{product_id}/toggle")
async def toggle_product(
    product_id: int,
    username: Annotated[str, Depends(verify_credentials)],
    session: AsyncSession = Depends(get_session),
):
    """Включить/выключить продукт"""
    await crud.toggle_product_active(session, product_id)
    return RedirectResponse(url="/admin/products", status_code=303)


@router.post("/{product_id}/update_price")
async def update_price(
    product_id: int,
    username: Annotated[str, Depends(verify_credentials)],
    session: AsyncSession = Depends(get_session),
    new_price: Decimal = Form(...),
):
    """Обновить цену продукта"""
    await crud.update_product_price(session, product_id, new_price)
    return RedirectResponse(url="/admin/products", status_code=303)
