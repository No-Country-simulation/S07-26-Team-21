from unittest.mock import AsyncMock, MagicMock
import pytest
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_evaluation import UserEvaluation
from app.schemas.benchmark_stats import BenchmarkStats
from app.services.stats_service import (
    StatsCache,
    get_platform_stats,
    stats_cache,
)


# ─────────────────────────────────────────────────────────────
# Unit Tests (stats_service.py con mocks)
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_stats_service_empty_db_returns_zeroes_and_all_pre_populated_keys():
    """
    Verifica que con BD vacía no falle por NULLs y devuelva todas las keys en 0.
    """
    mock_db = AsyncMock()
    # Mock para select(func.count) -> 0
    mock_count_res = MagicMock()
    mock_count_res.scalar.return_value = 0
    mock_db.execute.return_value = mock_count_res

    stats = await get_platform_stats(mock_db, bypass_cache=True)

    assert isinstance(stats, BenchmarkStats)
    assert stats.total_evaluations == 0
    assert stats.average_general_percentile == 0.0

    # Todas las regiones deben estar presentes con 0
    for r in ["latam", "usa", "europe", "apac"]:
        assert r in stats.by_region
        assert stats.by_region[r] == 0

    # Todos los tamaños deben estar presentes con 0
    for s in ["small", "medium", "large", "mega"]:
        assert s in stats.by_size
        assert stats.by_size[s] == 0

    # Todas las dimensiones deben estar presentes con 0.0
    for dim in ["visibilidad", "friccion", "latencia", "auto_cuantificacion", "bloqueantes"]:
        assert dim in stats.evaluations_by_dimension_strength
        assert stats.evaluations_by_dimension_strength[dim] == 0.0


@pytest.mark.asyncio
async def test_stats_service_aggregated_calculations():
    """
    Verifica el cálculo de agregaciones por región, tamaño y promedios por dimensión.
    """
    mock_db = AsyncMock()

    # 1. Conteo total: 3
    mock_count_res = MagicMock()
    mock_count_res.scalar.return_value = 3

    # 2. Regiones: latam: 2, usa: 1
    mock_region_res = MagicMock()
    mock_region_res.all.return_value = [("latam", 2), ("usa", 1)]

    # 3. Tamaños: small: 1, medium: 2
    mock_size_res = MagicMock()
    mock_size_res.all.return_value = [("small", 1), ("medium", 2)]

    # 4. Promedios: gen_pct=65.4, vis=4.0, fric=2.5, lat=3.2, auto=4.5, bloq=2.1
    mock_avg_res = MagicMock()
    mock_avg_res.first.return_value = (65.4, 4.0, 2.5, 3.2, 4.5, 2.1)

    mock_db.execute.side_effect = [
        mock_count_res,
        mock_region_res,
        mock_size_res,
        mock_avg_res,
    ]

    stats = await get_platform_stats(mock_db, bypass_cache=True)

    assert stats.total_evaluations == 3
    assert stats.by_region["latam"] == 2
    assert stats.by_region["usa"] == 1
    assert stats.by_region["europe"] == 0  # No presente en query -> debe ser 0
    assert stats.by_region["apac"] == 0

    assert stats.by_size["small"] == 1
    assert stats.by_size["medium"] == 2
    assert stats.by_size["large"] == 0
    assert stats.by_size["mega"] == 0

    assert stats.average_general_percentile == 65.4
    assert stats.evaluations_by_dimension_strength["visibilidad"] == 4.0
    assert stats.evaluations_by_dimension_strength["friccion"] == 2.5
    assert stats.evaluations_by_dimension_strength["latencia"] == 3.2
    assert stats.evaluations_by_dimension_strength["auto_cuantificacion"] == 4.5
    assert stats.evaluations_by_dimension_strength["bloqueantes"] == 2.1


def test_stats_cache_lifecycle():
    """
    Verifica el comportamiento del caché en memoria: set, is_valid, get y clear.
    """
    cache = StatsCache(ttl_seconds=3600)
    assert not cache.is_valid()
    assert cache.get() is None

    sample_stats = BenchmarkStats(
        total_evaluations=10,
        by_region={"latam": 10, "usa": 0, "europe": 0, "apac": 0},
        by_size={"small": 10, "medium": 0, "large": 0, "mega": 0},
        average_general_percentile=50.0,
        evaluations_by_dimension_strength={"visibilidad": 3.0, "friccion": 3.0, "latencia": 3.0, "auto_cuantificacion": 3.0, "bloqueantes": 3.0},
    )

    cache.set(sample_stats)
    assert cache.is_valid()
    assert cache.get() == sample_stats

    # Invalidación
    cache.clear()
    assert not cache.is_valid()
    assert cache.get() is None


# ─────────────────────────────────────────────────────────────
# Integration Tests (FastAPI Client + PostgreSQL real)
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_stats_endpoint_returns_200_and_full_schema(async_client: httpx.AsyncClient):
    """
    Verifica que GET /api/v1/benchmark/stats retorne 200 OK con el schema BenchmarkStats completo.
    """
    stats_cache.clear()
    response = await async_client.get("/api/v1/benchmark/stats")
    assert response.status_code == 200

    data = response.json()
    assert "total_evaluations" in data
    assert isinstance(data["total_evaluations"], int)
    assert "by_region" in data
    assert "latam" in data["by_region"]
    assert "by_size" in data
    assert "medium" in data["by_size"]
    assert "average_general_percentile" in data
    assert isinstance(data["average_general_percentile"], (int, float))
    assert "evaluations_by_dimension_strength" in data
    assert "visibilidad" in data["evaluations_by_dimension_strength"]


@pytest.mark.asyncio
async def test_post_submit_invalidates_stats_cache_and_updates_count(
    async_client: httpx.AsyncClient, db: AsyncSession
):
    """
    Verifica que tras un POST /submit, el caché se invalide y el contador total_evaluations
    se incremente en tiempo real.
    """
    # 1. Obtener conteo actual
    stats_cache.clear()
    initial_res = await async_client.get("/api/v1/benchmark/stats")
    assert initial_res.status_code == 200
    initial_count = initial_res.json()["total_evaluations"]

    # 2. Enviar una nueva evaluación válida
    payload = {
        "facility_size": "medium",
        "region": "latam",
        "p1": 4, "p2": 4, "p3": 4,
        "p4": 4, "p5": 4,
        "p6": 4, "p7": 4, "p8": 4,
        "p9": 4, "p10": 4,
        "p11": 4, "p12": 4, "p13": 4, "p14": 4, "p15": 4,
    }
    submit_res = await async_client.post("/api/v1/benchmark/submit", json=payload)
    assert submit_res.status_code == 201
    created_id = submit_res.json()["evaluation_id"]

    try:
        # 3. Consultar stats inmediatamente -> debe reflejar initial_count + 1
        updated_res = await async_client.get("/api/v1/benchmark/stats")
        assert updated_res.status_code == 200
        updated_count = updated_res.json()["total_evaluations"]
        assert updated_count == initial_count + 1

    finally:
        # Limpieza
        eval_record = await db.get(UserEvaluation, created_id)
        if eval_record:
            await db.delete(eval_record)
            await db.commit()
        stats_cache.clear()
