"""
Настройка подключения к базе данных
"""
import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

logger = logging.getLogger(__name__)


class DatabaseEngine:
    """Класс для управления подключением к БД"""

    def __init__(self, database_url: str, echo: bool = False):
        """
        Инициализация движка БД

        Args:
            database_url: URL подключения к PostgreSQL (postgresql+asyncpg://...)
            echo: Логировать ли SQL запросы
        """
        self.engine = create_async_engine(
            database_url,
            echo=echo,
            pool_pre_ping=True,  # Проверка соединения перед использованием
            pool_size=20,  # Размер пула соединений
            max_overflow=10,  # Дополнительные соединения при пиковой нагрузке
        )

        self.session_maker = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,  # Не сбрасывать объекты после commit
            autoflush=False,  # Не автофлаш при каждом запросе
        )

        logger.info("Database engine initialized")

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Получить сессию БД (используется как dependency в middleware/handlers)

        Yields:
            AsyncSession: Асинхронная сессия SQLAlchemy
        """
        async with self.session_maker() as session:
            try:
                yield session
            except Exception as e:
                logger.error(f"Session error: {e}")
                await session.rollback()
                raise
            finally:
                await session.close()

    async def dispose(self):
        """Закрыть все соединения с БД"""
        await self.engine.dispose()
        logger.info("Database engine disposed")


# Глобальный экземпляр (инициализируется в main.py после загрузки config)
db_engine: DatabaseEngine | None = None


def get_db_engine() -> DatabaseEngine:
    """Получить глобальный экземпляр движка БД"""
    if db_engine is None:
        raise RuntimeError("Database engine not initialized. Call init_db() first.")
    return db_engine


def init_db(database_url: str, echo: bool = False) -> DatabaseEngine:
    """
    Инициализировать глобальный экземпляр движка БД

    Args:
        database_url: URL подключения к PostgreSQL
        echo: Логировать ли SQL запросы

    Returns:
        DatabaseEngine: Инициализированный движок
    """
    global db_engine
    db_engine = DatabaseEngine(database_url, echo)
    return db_engine
