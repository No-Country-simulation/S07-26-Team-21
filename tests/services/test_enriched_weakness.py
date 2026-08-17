from unittest.mock import AsyncMock, MagicMock
import pytest
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_evaluation import UserEvaluation
from app.schemas.benchmark_output import MainWeaknessEnriched
from app.services.scoring_engine import (
    calculate_top_quartile_average,
    enrich_main_weakness,
    generate_benchmark_response,
)


# ─────────────────────────────────────────────────────────────
# Unit Tests (Cálculos de Top Quartile, Gap y Fallback)
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_calculate_top_quartile_average_cold_start_fallback():
    """
    Verifica que en Cold Start (sin usuarios con percentil > 75), tome el 100%
    del benchmark público (level_5_likert_equivalent).
    """
    mock_db = AsyncMock()
    mock_pub_res = MagicMock()
    mock_pub_res.scalar.return_value = 5.0
    mock_priv_res = MagicMock()
    mock_priv_res.scalar.return_value = None

    mock_db.execute.side_effect = [mock_pub_res, mock_priv_res]

    top_avg = await calculate_top_quartile_average("visibilidad", mock_db)
    assert top_avg == 5.0


@pytest.mark.asyncio
async def test_calculate_top_quartile_average_combines_fifty_fifty():
    """
    Verifica que con datos privados disponibles (percentil > 75), combine
    50% público + 50% privado.
    """
    mock_db = AsyncMock()
    mock_pub_res = MagicMock()
    mock_pub_res.scalar.return_value = 5.0
    mock_priv_res = MagicMock()
    mock_priv_res.scalar.return_value = 4.4

    mock_db.execute.side_effect = [mock_pub_res, mock_priv_res]

    top_avg = await calculate_top_quartile_average("friccion", mock_db)
    # (5.0 * 0.5) + (4.4 * 0.5) = 2.5 + 2.2 = 4.7
    assert top_avg == 4.7


@pytest.mark.asyncio
async def test_calculate_top_quartile_average_invalid_dimension_raises():
    """
    Verifica que una dimensión inexistente lance ValueError.
    """
    mock_db = AsyncMock()
    with pytest.raises(ValueError, match="no válida"):
        await calculate_top_quartile_average("dimension_inexistente", mock_db)


def test_gap_calculation_positive_and_non_negative_cap():
    """
    Verifica que el gap se calcule como max(0.0, top - user), evitando gaps negativos.
    """
    # Caso 1: Usuario por debajo de la élite
    enriched_1 = enrich_main_weakness(
        dimension="latencia",
        user_score=3.2,
        top_quartile_avg=4.8,
    )
    assert enriched_1.gap == 1.6
    assert enriched_1.user_score == 3.2
    assert enriched_1.top_quartile_average == 4.8

    # Caso 2: Usuario supera a la élite (gap nunca negativo)
    enriched_2 = enrich_main_weakness(
        dimension="visibilidad",
        user_score=5.0,
        top_quartile_avg=4.8,
    )
    assert enriched_2.gap == 0.0
    assert enriched_2.user_score == 5.0
    assert enriched_2.top_quartile_average == 4.8


def test_enrich_main_weakness_schema_and_static_recommendations():
    """
    Verifica la estructura del objeto MainWeaknessEnriched, sus recomendaciones
    estáticas y que llm_generated sea estrictamente False.
    """
    enriched = enrich_main_weakness(
        dimension="bloqueantes",
        user_score=2.4,
        top_quartile_avg=4.6,
    )

    assert isinstance(enriched, MainWeaknessEnriched)
    assert enriched.dimension == "bloqueantes"
    assert enriched.llm_generated is False
    assert len(enriched.recommendations) >= 3
    assert all(isinstance(r, str) for r in enriched.recommendations)

    # Compatibilidad con string y comparaciones de igualdad
    assert str(enriched) == "bloqueantes"
    assert enriched == "bloqueantes"


# ─────────────────────────────────────────────────────────────
# Integration Tests (PostgreSQL real y endpoints)
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_benchmark_response_integrates_enriched_main_weakness(db: AsyncSession):
    """
    Verifica que la orquestación asíncrona generate_benchmark_response
    retorne main_weakness como MainWeaknessEnriched con queries reales a PostgreSQL.
    """
    eval_record = UserEvaluation(
        facility_size="medium",
        region="latam",
        facility_type="Colocation",
        p1_visibilidad_herramientas=5,
        p2_visibilidad_dashboards=5,
        p3_visibilidad_telemetry=5,
        p4_friccion_energia=1,
        p5_friccion_cooling=1,
        p6_latencia_manual=5,
        p7_latencia_semi_auto=5,
        p8_latencia_full_auto=5,
        p9_auto_cuant_pue=5,
        p10_auto_cuant_utilizacion=5,
        p11_bloqueantes_staffing=5,
        p12_bloqueantes_supply=5,
        p13_bloqueantes_energy=5,
        p14_bloqueantes_regulacion=5,
        p15_bloqueantes_expertise=5,
    )
    db.add(eval_record)
    await db.commit()
    await db.refresh(eval_record)

    try:
        response = await generate_benchmark_response(eval_record.evaluation_id, db)

        assert isinstance(response.main_weakness, MainWeaknessEnriched)
        assert response.main_weakness.dimension == "friccion"
        assert response.main_weakness.user_score == 1.0
        assert response.main_weakness.top_quartile_average >= 1.0
        assert response.main_weakness.gap >= 0.0
        assert response.main_weakness.llm_generated is False
        assert len(response.main_weakness.recommendations) >= 3

    finally:
        await db.delete(eval_record)
        await db.commit()


@pytest.mark.asyncio
async def test_post_submit_endpoint_returns_201_with_enriched_main_weakness(
    async_client: httpx.AsyncClient, db: AsyncSession
):
    """
    Verifica que el endpoint POST /api/v1/benchmark/submit retorne
    el payload JSON con la estructura completa de main_weakness enriquecida.
    """
    payload = {
        "facility_size": "large",
        "region": "europe",
        "p1": 2, "p2": 2, "p3": 2,
        "p4": 5, "p5": 5,
        "p6": 5, "p7": 5, "p8": 5,
        "p9": 5, "p10": 5,
        "p11": 5, "p12": 5, "p13": 5, "p14": 5, "p15": 5,
    }

    res = await async_client.post("/api/v1/benchmark/submit", json=payload)
    assert res.status_code == 201

    data = res.json()
    assert "main_weakness" in data
    mw_data = data["main_weakness"]

    assert isinstance(mw_data, dict)
    assert mw_data["dimension"] == "visibilidad"
    assert mw_data["user_score"] == 2.0
    assert "top_quartile_average" in mw_data
    assert "gap" in mw_data
    assert mw_data["gap"] >= 0.0
    assert mw_data["llm_generated"] is False
    assert len(mw_data["recommendations"]) >= 3

    # Limpieza
    created_id = data["evaluation_id"]
    eval_record = await db.get(UserEvaluation, created_id)
    if eval_record:
        await db.delete(eval_record)
        await db.commit()
