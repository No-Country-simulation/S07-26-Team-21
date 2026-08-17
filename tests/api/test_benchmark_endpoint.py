"""
tests/api/test_benchmark_endpoint.py

Tests E2E para el endpoint POST /api/v1/benchmark/submit (US-9).
Usa httpx.AsyncClient y la base de datos real con session override.
"""

from uuid import UUID
import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_evaluation import UserEvaluation


VALID_BENCHMARK_PAYLOAD = {
    "facility_size": "medium",
    "region": "latam",
    "facility_type": "Enterprise",
    "p1": 4,
    "p2": 3,
    "p3": 5,
    "p4": 2,
    "p5": 2,
    "p6": 3,
    "p7": 4,
    "p8": 3,
    "p9": 4,
    "p10": 5,
    "p11": 1,
    "p12": 2,
    "p13": 1,
    "p14": 2,
    "p15": 1,
}


@pytest.mark.asyncio
async def test_submit_benchmark_e2e_success_returns_201(
    async_client: httpx.AsyncClient,
    db: AsyncSession,
):
    """
    Criterio US-9:
    1. POST /api/v1/benchmark/submit con payload válido.
    2. Retorna Status 201 Created.
    3. Retorna BenchmarkResponse con las 6 secciones requeridas.
    4. Persiste la entidad UserEvaluation en la base de datos.
    """
    response = await async_client.post(
        "/api/v1/benchmark/submit",
        json=VALID_BENCHMARK_PAYLOAD,
    )

    assert response.status_code == 201
    data = response.json()

    # 1. Validar evaluation_id UUID
    assert "evaluation_id" in data
    eval_id = UUID(data["evaluation_id"])

    # 2. Validar user_context
    assert data["user_context"]["facility_size"] == "medium"
    assert data["user_context"]["region"] == "latam"

    # 3. Validar scores_likert
    assert "scores_likert" in data
    scores = data["scores_likert"]
    assert scores["visibilidad"] == pytest.approx(4.0)  # (4+3+5)/3 = 4.0
    assert scores["friccion"] == pytest.approx(2.0)     # (2+2)/2 = 2.0
    assert scores["latencia"] == pytest.approx(3.33, abs=0.01) # (3+4+3)/3 = 3.33
    assert scores["auto_cuantificacion"] == pytest.approx(4.5) # (4+5)/2 = 4.5
    assert scores["bloqueantes"] == pytest.approx(1.4, abs=0.01) # (1+2+1+2+1)/5 = 1.4

    # 4. Validar percentiles
    assert "percentiles" in data
    percentiles = data["percentiles"]
    assert 0 <= percentiles["visibilidad"] <= 100
    assert 0 <= percentiles["friccion"] <= 100
    assert 0 <= percentiles["latencia"] <= 100
    assert 0 <= percentiles["auto_cuantificacion"] <= 100
    assert 0 <= percentiles["bloqueantes"] <= 100
    assert 0 <= percentiles["general"] <= 100

    # 5. Validar debilidad principal
    assert "main_weakness" in data
    mw_dim = data["main_weakness"]["dimension"] if isinstance(data["main_weakness"], dict) else data["main_weakness"]
    assert mw_dim in [
        "visibilidad",
        "latencia",
        "friccion",
        "auto_cuantificacion",
        "bloqueantes",
    ]


    # 6. Validar rebalanceo
    assert "rebalancing_status" in data
    rebalancing = data["rebalancing_status"]
    assert isinstance(rebalancing["weight_public"], float)
    assert isinstance(rebalancing["weight_private"], float)
    assert rebalancing["weight_public"] + rebalancing["weight_private"] == pytest.approx(1.0)

    # 7. Validar persistencia real en PostgreSQL
    result = await db.execute(
        select(UserEvaluation).where(UserEvaluation.evaluation_id == eval_id)
    )
    saved_eval = result.scalar_one_or_none()
    assert saved_eval is not None
    assert saved_eval.facility_size == "medium"
    assert saved_eval.region == "latam"
    assert saved_eval.p1_visibilidad_herramientas == 4


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_p1", [0, 6, -1, 10, "string_invalido"])
async def test_submit_benchmark_invalid_likert_returns_422(
    async_client: httpx.AsyncClient,
    invalid_p1,
):
    """
    Criterio US-9: Si una pregunta Likert está fuera del rango [1, 5] o tiene tipo incorrecto,
    retorna 422 Unprocessable Entity.
    """
    payload = {**VALID_BENCHMARK_PAYLOAD, "p1": invalid_p1}
    response = await async_client.post(
        "/api/v1/benchmark/submit",
        json=payload,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_submit_benchmark_invalid_enum_returns_422(
    async_client: httpx.AsyncClient,
):
    """
    Criterio US-9: Si un enum de contexto es inválido, retorna 422.
    """
    payload = {**VALID_BENCHMARK_PAYLOAD, "facility_size": "gigantic"}
    response = await async_client.post(
        "/api/v1/benchmark/submit",
        json=payload,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_submit_benchmark_missing_required_field_returns_422(
    async_client: httpx.AsyncClient,
):
    """
    Criterio US-9: Si falta un campo requerido (ej. p15), retorna 422.
    """
    payload = {k: v for k, v in VALID_BENCHMARK_PAYLOAD.items() if k != "p15"}
    response = await async_client.post(
        "/api/v1/benchmark/submit",
        json=payload,
    )
    assert response.status_code == 422
