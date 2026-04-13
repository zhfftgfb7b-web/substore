"""
Middleware для предоставления сессии БД в handlers
"""
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from database.engine import get_db_engine


class DatabaseMiddleware(BaseMiddleware):
    """Middleware добавляющий сессию БД в data handlers"""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """
        Создаёт сессию БД для каждого update и передаёт её в handler

        Args:
            handler: Следующий handler в цепочке
            event: Telegram event (Message, CallbackQuery, etc.)
            data: Словарь данных для передачи в handler

        Returns:
            Результат выполнения handler
        """
        db_engine = get_db_engine()

        async for session in db_engine.get_session():
            # Добавляем сессию в data для доступа из handlers
            data["session"] = session
            return await handler(event, data)
