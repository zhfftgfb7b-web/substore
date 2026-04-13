"""
Роут Keys админ-панели
"""
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from admin_panel.auth import verify_credentials
from admin_panel.routes.dashboard import get_session
from database import crud
from database.models import DeliveryTypeEnum

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def keys_page(
    request: Request,
    username: Annotated[str, Depends(verify_credentials)],
    session: AsyncSession = Depends(get_session),
):
    """Страница управления ключами"""
    products = await crud.get_all_products(session, active_only=False)

    # Статистика по ключам для каждого продукта
    key_stats = []
    for product in products:
        if product.delivery_type == DeliveryTypeEnum.auto:
            stats = await crud.get_key_stats(session, product.id)
            key_stats.append({
                "product": product,
                **stats,
            })

    return templates.TemplateResponse(
        "keys.html",
        {
            "request": request,
            "products": [p for p in products if p.delivery_type == DeliveryTypeEnum.auto],
            "key_stats": key_stats,
        },
    )


@router.post("/add")
async def add_keys(
    username: Annotated[str, Depends(verify_credentials)],
    session: AsyncSession = Depends(get_session),
    product_id: int = Form(...),
    keys_text: str = Form(...),
):
    """Добавить ключи в пул"""
    # Парсим ключи
    keys = [line.strip() for line in keys_text.split("\n") if line.strip()]

    if keys:
        await crud.add_keys_to_pool(session, product_id, keys)

    return RedirectResponse(url="/admin/keys", status_code=303)
