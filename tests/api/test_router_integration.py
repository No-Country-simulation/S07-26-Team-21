"""
tests/api/test_router_integration.py

Tests de integración de routers y verificación de OpenAPI docs.
Verifica que todos los endpoints estén disponibles en /api/v1/benchmark
y que /api/v1/health y /docs funcionen correctamente.
"""

import httpx
import pytest


@pytest.mark.asyncio
async def test_health_endpoint_returns_200(async_client: httpx.AsyncClient):
    """
    Criterio de Aceptación:
    GET /api/v1/health sigue funcionando correctamente y responde 200 OK.
    """
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "BENCHMARK·DC Engine" in data["service"]


@pytest.mark.asyncio
async def test_openapi_schema_contains_benchmark_and_health_routes(
    async_client: httpx.AsyncClient,
):
    """
    Criterio de Aceptación:
    Documentación OpenAPI en /api/v1/openapi.json expone los endpoints
    bajo el prefijo /api/v1/benchmark y /api/v1/health.
    """
    response = await async_client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    schema = response.json()

    # Validar que existan rutas registradas
    assert "paths" in schema
    paths = schema["paths"]

    # 1. Ruta de health
    assert "/api/v1/health" in paths
    assert "get" in paths["/api/v1/health"]

    # 2. Ruta de benchmark submit
    assert "/api/v1/benchmark/submit" in paths
    assert "post" in paths["/api/v1/benchmark/submit"]


@pytest.mark.asyncio
async def test_root_endpoint_returns_welcome_and_docs_link(
    async_client: httpx.AsyncClient,
):
    """
    Verifica que el endpoint raíz GET / responda 200 OK y guíe hacia la documentación.
    """
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert data["docs"] == "/docs"


@pytest.mark.asyncio
async def test_swagger_docs_endpoint_returns_200(
    async_client: httpx.AsyncClient,
):
    """
    Criterio de Aceptación:
    Documentación Swagger UI en /docs responde 200 OK.
    """
    response = await async_client.get("/docs")
    assert response.status_code == 200
    assert "html" in response.headers.get("content-type", "").lower()
