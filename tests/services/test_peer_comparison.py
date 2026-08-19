import uuid
from unittest.mock import AsyncMock, MagicMock
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_evaluation import UserEvaluation
from app.schemas.benchmark_input import FacilitySizeEnum, RegionEnum
from app.schemas.benchmark_output import PeerComparison
from app.services.scoring_engine import (
    generate_benchmark_response,
    get_peer_stats,
)


# ─────────────────────────────────────────────────────────────
# Unit Tests (con mocks de BD)
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_peer_stats_no_context_returns_zero_peers_and_disclaimer():
    """
    Verifica que si facility_size o region son None, retorne 0 peers y disclaimer informativo.
    """
    mock_db = AsyncMock()
    result = await get_peer_stats(
        dimension="visibilidad",
        facility_size=None,
        region="latam",
        user_score=3.5,
        db=mock_db,
    )
    assert isinstance(result, PeerComparison)
    assert result.peers_count == 0
    assert result.peer_average_score is None
    assert result.your_score == 3.5
    assert result.gap_vs_peers is None
    assert result.percentile_vs_peers is None
    assert result.disclaimer == "No hay suficientes datos de peers"


@pytest.mark.asyncio
async def test_peer_stats_zero_peers_returns_none_metrics():
    """
    Verifica que si no hay registros coincidentes en la cohorte, retorne 0 peers y disclaimer.
    """
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_db.execute.return_value = mock_result

    result = await get_peer_stats(
        dimension="friccion",
        facility_size="medium",
        region="latam",
        user_score=2.0,
        db=mock_db,
    )
    assert result.peers_count == 0
    assert result.peer_average_score is None
    assert result.gap_vs_peers is None
    assert result.percentile_vs_peers is None
    assert result.disclaimer == "No hay suficientes datos de peers"


@pytest.mark.asyncio
@pytest.mark.parametrize("peers_scores", [[(3.0,)], [(2.0,), (4.0,)]])
async def test_peer_stats_k_anonymity_under_three_peers_returns_privacy_disclaimer(peers_scores):
    """
    US-17 K-anonimato: Si hay 1 o 2 peers, NO se calculan métricas para proteger
    el anonimato estadístico y se muestra disclaimer específico.
    """
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = peers_scores
    mock_db.execute.return_value = mock_result

    result = await get_peer_stats(
        dimension="latencia",
        facility_size=FacilitySizeEnum.MEDIUM,
        region=RegionEnum.USA,
        user_score=3.0,
        db=mock_db,
    )
    assert result.peers_count == len(peers_scores)
    assert result.peer_average_score is None
    assert result.gap_vs_peers is None
    assert result.percentile_vs_peers is None
    assert result.disclaimer == "Muestra insuficiente para garantizar el anonimato estadístico"


@pytest.mark.asyncio
async def test_peer_stats_three_peers_sample_returns_metrics_and_limited_disclaimer():
    """
    Si hay 3 o 4 peers, se calculan las métricas pero se adjunta disclaimer de 'Muestra limitada'.
    """
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = [(2.0,), (3.0,), (4.0,)]  # promedio = 3.0
    mock_db.execute.return_value = mock_result

    result = await get_peer_stats(
        dimension="auto_cuantificacion",
        facility_size="small",
        region="europe",
        user_score=3.5,
        db=mock_db,
    )
    assert result.peers_count == 3
    assert result.peer_average_score == 3.0
    assert result.your_score == 3.5
    assert result.gap_vs_peers == 0.5  # 3.5 - 3.0
    # count_lower: 2.0 y 3.0 son menores que 3.5 (2 de 3 = 66.6% -> 67%)
    assert result.percentile_vs_peers == 67
    assert result.disclaimer == "Muestra limitada"


@pytest.mark.asyncio
async def test_peer_stats_ten_peers_standard_calculation():
    """
    Verifica el cálculo estándar con 10 peers (>=5 peers -> disclaimer=None).
    """
    mock_db = AsyncMock()
    mock_result = MagicMock()
    # 10 scores de peers
    scores = [1.0, 2.0, 2.5, 3.0, 3.5, 4.0, 4.0, 4.5, 5.0, 5.0]
    mock_result.all.return_value = [(s,) for s in scores]
    mock_db.execute.return_value = mock_result

    # user_score = 4.0 -> promedio de peers = 3.45, gap = +0.55
    # estrictamente menores que 4.0 son [1.0, 2.0, 2.5, 3.0, 3.5] (5 de 10 = 50%)
    result = await get_peer_stats(
        dimension="bloqueantes",
        facility_size="large",
        region="latam",
        user_score=4.0,
        db=mock_db,
    )
    assert result.peers_count == 10
    assert result.peer_average_score == 3.45
    assert result.your_score == 4.0
    assert result.gap_vs_peers == 0.55
    assert result.percentile_vs_peers == 50
    assert result.disclaimer is None


@pytest.mark.asyncio
async def test_peer_stats_extreme_boundaries_zero_and_hundred_percentiles():
    """
    Verifica los percentiles extremos 0% y 100% frente a peers.
    """
    mock_db = AsyncMock()

    # Caso 0%: todos los peers tienen score superior
    mock_result_zero = MagicMock()
    mock_result_zero.all.return_value = [(3.0,), (4.0,), (5.0,), (5.0,), (5.0,)]
    mock_db.execute.return_value = mock_result_zero

    res_zero = await get_peer_stats("visibilidad", "mega", "apac", 1.0, mock_db)
    assert res_zero.percentile_vs_peers == 0
    assert res_zero.gap_vs_peers == -3.4

    # Caso 100%: todos los peers tienen score estrictamente inferior
    mock_result_hundred = MagicMock()
    mock_result_hundred.all.return_value = [(1.0,), (2.0,), (3.0,), (4.0,), (4.5,)]
    mock_db.execute.return_value = mock_result_hundred

    res_hundred = await get_peer_stats("visibilidad", "mega", "apac", 5.0, mock_db)
    assert res_hundred.percentile_vs_peers == 100
    assert res_hundred.gap_vs_peers == 2.1


@pytest.mark.asyncio
async def test_peer_stats_invalid_dimension_raises_value_error():
    """
    Verifica que pasar una dimensión no reconocida levante ValueError.
    """
    mock_db = AsyncMock()
    with pytest.raises(ValueError) as exc_info:
        await get_peer_stats("cooling_capacity", "small", "latam", 3.0, mock_db)

    assert "Dimensión inválida" in str(exc_info.value)


# ─────────────────────────────────────────────────────────────
# Integration Tests (con Base de Datos PostgreSQL real)
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_peer_comparison_isolation_by_region_and_size(db: AsyncSession):
    """
    Verifica en PostgreSQL real que las consultas de peers filtren estrictamente
    por facility_size y region, sin mezclar cohortes.
    """
    # 4 peers en latam/small
    latam_peers = [
        UserEvaluation(
            facility_size="small",
            region="latam",
            p1_visibilidad_herramientas=3, p2_visibilidad_dashboards=3, p3_visibilidad_telemetry=3,
            p4_friccion_energia=3, p5_friccion_cooling=3,
            p6_latencia_manual=3, p7_latencia_semi_auto=3, p8_latencia_full_auto=3,
            p9_auto_cuant_pue=3, p10_auto_cuant_utilizacion=3,
            p11_bloqueantes_staffing=3, p12_bloqueantes_supply=3, p13_bloqueantes_energy=3,
            p14_bloqueantes_regulacion=3, p15_bloqueantes_expertise=3,
            score_visibilidad=score_val,
        )
        for score_val in [2.0, 2.5, 3.0, 3.5]
    ]

    # 5 peers en usa/large (que NO deben afectar a latam/small)
    usa_peers = [
        UserEvaluation(
            facility_size="large",
            region="usa",
            p1_visibilidad_herramientas=5, p2_visibilidad_dashboards=5, p3_visibilidad_telemetry=5,
            p4_friccion_energia=5, p5_friccion_cooling=5,
            p6_latencia_manual=5, p7_latencia_semi_auto=5, p8_latencia_full_auto=5,
            p9_auto_cuant_pue=5, p10_auto_cuant_utilizacion=5,
            p11_bloqueantes_staffing=5, p12_bloqueantes_supply=5, p13_bloqueantes_energy=5,
            p14_bloqueantes_regulacion=5, p15_bloqueantes_expertise=5,
            score_visibilidad=5.0,
        )
        for _ in range(5)
    ]

    all_created = latam_peers + usa_peers
    for item in all_created:
        db.add(item)
    await db.commit()

    try:
        # Consultar peers para un usuario latam/small con score 3.0
        stats_latam = await get_peer_stats(
            dimension="visibilidad",
            facility_size="small",
            region="latam",
            user_score=3.0,
            db=db,
        )

        assert stats_latam.peers_count == 4
        assert stats_latam.peer_average_score == 2.75  # (2.0+2.5+3.0+3.5)/4
        assert stats_latam.your_score == 3.0
        assert stats_latam.gap_vs_peers == 0.25
        # Menores que 3.0: 2.0 y 2.5 (2 de 4 = 50%)
        assert stats_latam.percentile_vs_peers == 50
        assert stats_latam.disclaimer == "Muestra limitada"

    finally:
        for item in all_created:
            await db.delete(item)
        await db.commit()


@pytest.mark.asyncio
async def test_peer_comparison_integrated_in_generate_benchmark_response(db: AsyncSession):
    """
    Verifica que generate_benchmark_response incluya la sección peer_comparison poblada.
    """
    test_user = UserEvaluation(
        facility_size="medium",
        region="latam",
        p1_visibilidad_herramientas=4, p2_visibilidad_dashboards=4, p3_visibilidad_telemetry=4,
        p4_friccion_energia=2, p5_friccion_cooling=2,  # friccion = 2.0 (debilidad principal)
        p6_latencia_manual=4, p7_latencia_semi_auto=4, p8_latencia_full_auto=4,
        p9_auto_cuant_pue=4, p10_auto_cuant_utilizacion=4,
        p11_bloqueantes_staffing=4, p12_bloqueantes_supply=4, p13_bloqueantes_energy=4,
        p14_bloqueantes_regulacion=4, p15_bloqueantes_expertise=4,
    )
    db.add(test_user)
    await db.commit()
    await db.refresh(test_user)

    try:
        response = await generate_benchmark_response(test_user.evaluation_id, db)
        assert response.main_weakness == "friccion"
        assert response.peer_comparison is not None
        assert response.peer_comparison.your_score == 2.0
        assert isinstance(response.peer_comparison.peers_count, int)
    finally:
        await db.delete(test_user)
        await db.commit()
