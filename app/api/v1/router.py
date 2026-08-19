from fastapi import APIRouter
from app.api.v1.endpoints import benchmark, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(benchmark.router, prefix="/benchmark", tags=["Benchmark"])