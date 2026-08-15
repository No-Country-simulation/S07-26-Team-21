"""
tests/test_exceptions.py

Suite de pruebas para la US-12: Manejo uniforme y consistente de excepciones.
Verifica que todos los exception handlers registrados en main.py retornen
respuestas JSON con {"detail": "..."} y protejan la información interna de la BD.
"""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from starlette.testclient import TestClient
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.main import app
from app.exceptions import (
    DatabaseException,
    EvaluationNotFoundException,
    InvalidPayloadException,
)


@pytest.fixture
def test_app_with_faulty_endpoints():
    """
    App auxiliar con endpoints de prueba para disparar cada tipo de excepción
    y validar los handlers registrados globalmente en app.
    """
    @app.get("/test-error/404-not-found")
    async def trigger_not_found():
        raise EvaluationNotFoundException(uuid.uuid4())

    @app.get("/test-error/422-invalid-payload")
    async def trigger_invalid_payload():
        raise InvalidPayloadException("El parámetro de consulta es inválido.")

    @app.get("/test-error/500-database-exception")
    async def trigger_database_exception():
        raise DatabaseException(
            detail="Error interno del servidor al procesar la solicitud.",
            original_error=Exception("Connection refused to database"),
        )

    @app.get("/test-error/500-sqlalchemy-error")
    async def trigger_sqlalchemy_error():
        raise OperationalError(
            statement="SELECT * FROM secret_table WHERE id = 1",
            params={},
            orig=Exception("FATAL: password authentication failed for user 'postgres'"),
        )

    @app.get("/test-error/500-unhandled-exception")
    async def trigger_unhandled_exception():
        raise RuntimeError("Unexpected failure in background process")

    return app


@pytest.mark.asyncio
async def test_evaluation_not_found_handler_returns_404_json(test_app_with_faulty_endpoints):
    """
    Verifica que EvaluationNotFoundException retorne status 404 y JSON con {"detail": "..."}.
    """
    transport = ASGITransport(app=test_app_with_faulty_endpoints)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/test-error/404-not-found")

    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "no encontrada" in data["detail"]


@pytest.mark.asyncio
async def test_invalid_payload_handler_returns_422_json(test_app_with_faulty_endpoints):
    """
    Verifica que InvalidPayloadException retorne status 422 y JSON con {"detail": "..."}.
    """
    transport = ASGITransport(app=test_app_with_faulty_endpoints)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/test-error/422-invalid-payload")

    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    assert data["detail"] == "El parámetro de consulta es inválido."


@pytest.mark.asyncio
async def test_request_validation_error_returns_422_json(async_client: AsyncClient):
    """
    Verifica que enviar un payload inválido al endpoint real POST /submit
    retorne status 422 con la clave 'detail'.
    """
    invalid_payload = {
        "facility_size": "super_giant",  # Inválido
        "region": "latam",
        "p1": 99,  # Fuera de rango
    }
    response = await async_client.post("/api/v1/benchmark/submit", json=invalid_payload)
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    assert isinstance(data["detail"], list)


@pytest.mark.asyncio
async def test_database_exception_handler_returns_500_safe_json(test_app_with_faulty_endpoints):
    """
    Verifica que DatabaseException retorne status 500 con mensaje genérico seguro.
    """
    client = TestClient(test_app_with_faulty_endpoints, raise_server_exceptions=False)
    response = client.get("/test-error/500-database-exception")

    assert response.status_code == 500
    data = response.json()
    assert "detail" in data
    assert data["detail"] == "Error interno del servidor al procesar la solicitud."


@pytest.mark.asyncio
async def test_sqlalchemy_error_handler_returns_500_without_leaking_sql(test_app_with_faulty_endpoints):
    """
    Verifica que SQLAlchemyError retorne status 500 y NO filtre sentencias SQL ni nombres de tablas o usuarios.
    """
    client = TestClient(test_app_with_faulty_endpoints, raise_server_exceptions=False)
    response = client.get("/test-error/500-sqlalchemy-error")

    assert response.status_code == 500
    data = response.json()
    assert "detail" in data
    assert data["detail"] == "Error interno del servidor al procesar la solicitud."
    # Aseguramos que detalles sensibles del SQL o del motor no se envían en el JSON
    assert "secret_table" not in str(data)
    assert "password authentication failed" not in str(data)


@pytest.mark.asyncio
async def test_unhandled_exception_returns_500_safe_json(test_app_with_faulty_endpoints):
    """
    Verifica que cualquier excepción no controlada retorne status 500 con mensaje genérico.
    """
    client = TestClient(test_app_with_faulty_endpoints, raise_server_exceptions=False)
    response = client.get("/test-error/500-unhandled-exception")

    assert response.status_code == 500
    data = response.json()
    assert "detail" in data
    assert data["detail"] == "Error interno no controlado."


