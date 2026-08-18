import logging
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.router import api_router
from app.core.config import settings
from app.exceptions import (
    BenchmarkException,
    DatabaseException,
    EvaluationNotFoundException,
    InvalidPayloadException,
)

logger = logging.getLogger("benchmark.api")

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# Configuración de CORS segura para permitir conexiones desde el Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# ─────────────────────────────────────────────────────────────
# Exception Handlers Globales (US-12)
# ─────────────────────────────────────────────────────────────

@app.exception_handler(EvaluationNotFoundException)
async def evaluation_not_found_handler(
    request: Request, exc: EvaluationNotFoundException
) -> JSONResponse:
    """Manejo uniforme de evaluaciones no encontradas (404)."""
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": exc.detail},
    )


@app.exception_handler(InvalidPayloadException)
async def invalid_payload_handler(
    request: Request, exc: InvalidPayloadException
) -> JSONResponse:
    """Manejo uniforme de errores de validación de negocio (422)."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Manejo uniforme de errores de validación de Pydantic/FastAPI (422)."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
    )


@app.exception_handler(DatabaseException)
async def database_exception_handler(
    request: Request, exc: DatabaseException
) -> JSONResponse:
    """Manejo seguro de errores de base de datos con logging privado (500)."""
    logger.error(
        f"DatabaseException en {request.method} {request.url.path}: {exc.detail} | Original: {exc.original_error}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Error interno del servidor al procesar la solicitud."},
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(
    request: Request, exc: SQLAlchemyError
) -> JSONResponse:
    """Manejo seguro de errores de SQLAlchemy sin exponer queries ni tablas (500)."""
    logger.error(
        f"SQLAlchemyError en {request.method} {request.url.path}: {exc}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Error interno del servidor al procesar la solicitud."},
    )


@app.exception_handler(Exception)
async def general_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Manejo catch-all para cualquier excepción imprevista (500)."""
    logger.error(
        f"Excepción no controlada en {request.method} {request.url.path}: {exc}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Error interno no controlado."},
    )


# Incluir el Router de la API v1
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    return {
        "message": f"Bienvenido a {settings.PROJECT_NAME}",
        "docs": "/docs",
    }