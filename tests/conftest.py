from typing import AsyncGenerator
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from app.core.config import settings


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    """
    Fixture que provee una sesión asíncrona real de base de datos para tests de integración.
    Usa NullPool para evitar que conexiones asyncpg queden atadas a un event loop cerrado entre tests.
    """
    test_engine = create_async_engine(
        settings.ASYNC_DATABASE_URL,
        poolclass=NullPool,
        future=True,
    )
    test_session_maker = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with test_session_maker() as session:
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()
    await test_engine.dispose()
