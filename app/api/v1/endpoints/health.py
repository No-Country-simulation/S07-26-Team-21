from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["System"])
async def health_check():
    """Endpoint para verificar que la API está corriendo correctamente."""
    return {"status": "ok", "service": "BENCHMARK·DC Engine API"}