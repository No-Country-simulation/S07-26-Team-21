from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# 1. Crear el Motor (Engine) Asíncrono de SQLAlchemy
engine = create_async_engine(
    settings.ASYNC_DATABASE_URL,
    echo=False,  # Cambiar a True si deseas ver en consola las queries SQL generadas
    future=True,
)

# 2. Fábrica de Sesiones Asíncronas (Session Factory)
AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


# 3. Clase Base para los Modelos ORM
class Base(DeclarativeBase):
    pass


# 4. Inyección de Dependencia para la Sesión de Base de Datos
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Generador asíncrono que provee una sesión de BDD y garantiza su cierre."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()