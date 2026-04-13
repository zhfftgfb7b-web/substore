"""
Роут Users админ-панели
"""
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from admin_panel.auth import verify_credentials
from admin_panel.routes.dashboard import get_session
from database import crud
from sqlalchemy import select
from database.models import User

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def users_page(
    request: Request,
    username: Annotated[str, Depends(verify_credentials)],
    session: AsyncSession = Depends(get_session),
    search: str = None,
):
    """Страница управления пользователями"""
    if search:
        users = await crud.search_users(session, search)
    else:
        # Получаем последних 50 пользователей
        result = await session.execute(
            select(User).order_by(User.created_at.desc()).limit(50)
        )
        users = list(result.scalars().all())

    # Для каждого пользователя получаем статистику заказов
    user_stats = []
    for user in users:
        orders = await crud.get_user_orders(session, user.id, limit=1000)
        total_spent = sum(float(o.amount) for o in orders if o.status.value in ["paid", "delivered"])

        user_stats.append({
            "user": user,
            "orders_count": len(orders),
            "total_spent": total_spent,
        })

    return templates.TemplateResponse(
        "users.html",
        {
            "request": request,
            "user_stats": user_stats,
            "search": search or "",
        },
    )


@router.post("/{user_id}/ban")
async def ban_user(
    user_id: int,
    username: Annotated[str, Depends(verify_credentials)],
    session: AsyncSession = Depends(get_session),
):
    """Заблокировать пользователя"""
    await crud.ban_user(session, user_id, banned=True)
    return RedirectResponse(url="/admin/users", status_code=303)


@router.post("/{user_id}/unban")
async def unban_user(
    user_id: int,
    username: Annotated[str, Depends(verify_credentials)],
    session: AsyncSession = Depends(get_session),
):
    """Разблокировать пользователя"""
    await crud.ban_user(session, user_id, banned=False)
    return RedirectResponse(url="/admin/users", status_code=303)
