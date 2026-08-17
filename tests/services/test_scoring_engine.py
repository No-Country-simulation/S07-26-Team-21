"""
tests/test_scoring_engine.py

Unit tests para app/services/scoring_engine.py (US-4, US-5 y US-6).
Correr con: pytest tests/services/test_scoring_engine.py -v
"""

from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_evaluation import UserEvaluation
from app.schemas.benchmark_input import (
    BenchmarkSubmitSchema,
    FacilitySizeEnum,
    RegionEnum,
)
from app.schemas.benchmark_output import BenchmarkResponse, MainWeaknessEnriched

from app.services.scoring_engine import (
    build_result_response,
    calculate_dimension_percentile,
    calculate_dimension_score,
    calculate_rebalancing_weights,
    compute_dimension_scores,
    compute_percentiles,
    generate_benchmark_response,
    generate_recommendations,
    get_main_weakness,
    identify_main_weakness,
    normalize_score,
    process_evaluation,
    _percentile_from_scores,
)






# ─────────────────────────────────────────────────────────────
# US-4: calculate_dimension_score (promedio de Likert)
# ─────────────────────────────────────────────────────────────

def test_all_ones_returns_one():
    assert calculate_dimension_score([1, 1, 1]) == 1.0


def test_all_fives_returns_five():
    assert calculate_dimension_score([5, 5, 5]) == 5.0


def test_mixed_values_averages_correctly():
    # Ejemplo de la US-4: Visibilidad (3+2+4)/3 = 3.0
    assert calculate_dimension_score([3, 2, 4]) == 3.0


def test_two_question_dimension():
    # Ejemplo: Fricción (4+4)/2 = 4.0
    assert calculate_dimension_score([4, 4]) == 4.0


def test_five_question_dimension():
    # Ejemplo: Bloqueantes (3+2+4+3+2)/5 = 2.8
    assert calculate_dimension_score([3, 2, 4, 3, 2]) == pytest.approx(2.8)


def test_empty_list_raises_value_error():
    with pytest.raises(ValueError):
        calculate_dimension_score([])


# ─────────────────────────────────────────────────────────────
# US-5: _percentile_from_scores (función pura, sin BD)
# ─────────────────────────────────────────────────────────────

def test_percentile_matches_us5_example():
    # Criterio US-5: user_score=3 en [1,1,1,3,3,3,5,5,5] → 33%
    assert _percentile_from_scores(3, [1, 1, 1, 3, 3, 3, 5, 5, 5]) == 33


def test_percentile_thirty_five_benchmarks_and_one_user():
    # Criterio US-5: Con 1 usuario (2.67 en latencia) y 35 benchmarks (1,3,5): retorna ~33%
    public_scores = [1.0] * 35 + [3.0] * 35 + [5.0] * 35  # 105 scores
    private_scores = [2.67]  # 1 score privado
    all_scores = public_scores + private_scores  # Total = 106
    # Scores menores a 2.67 son los 35 unos -> 35/106 * 100 = 33.018% -> 33%
    assert _percentile_from_scores(2.67, all_scores) == 33


def test_percentile_empty_dataset_returns_fifty():
    # Criterio US-5: Edge case total=0 → 50 por defecto
    assert _percentile_from_scores(3, []) == 50


def test_percentile_all_scores_higher_returns_zero():
    assert _percentile_from_scores(1, [2, 3, 4, 5]) == 0


def test_percentile_all_scores_lower_returns_hundred():
    assert _percentile_from_scores(5, [1, 2, 3, 4]) == 100


# ─────────────────────────────────────────────────────────────
# US-5: calculate_dimension_percentile (async, con sesión mockeada)
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_calculate_dimension_percentile_combines_public_and_private():
    """
    Simula 1 benchmark público (niveles 1, 3, 5) + 1 score privado en 3.0
    para la dimensión "latencia". user_score=3.0.

    all_scores combinados = [1, 3, 5, 3.0] → total=4
    Scores menores a 3.0: solo el 1 → 1/4 = 25%
    """
    public_result = MagicMock()
    public_result.all.return_value = [(1, 3, 5)]

    private_result = MagicMock()
    private_result.all.return_value = [(3.0,)]

    mock_db = AsyncMock()
    mock_db.execute.side_effect = [public_result, private_result]

    percentile = await calculate_dimension_percentile("latencia", 3.0, mock_db)

    assert percentile == 25
    assert mock_db.execute.call_count == 2


@pytest.mark.asyncio
async def test_calculate_dimension_percentile_thirty_five_benchmarks_async():
    """
    Test asíncrono que simula exactamente 35 benchmarks de latencia y 1 usuario previo en 2.67.
    """
    # 35 filas con (1, 3, 5)
    public_rows = [(1, 3, 5)] * 35
    public_result = MagicMock()
    public_result.all.return_value = public_rows

    private_result = MagicMock()
    private_result.all.return_value = [(2.67,)]

    mock_db = AsyncMock()
    mock_db.execute.side_effect = [public_result, private_result]

    percentile = await calculate_dimension_percentile("latencia", 2.67, mock_db)

    assert percentile == 33


@pytest.mark.asyncio
async def test_calculate_dimension_percentile_invalid_dimension_raises():
    mock_db = AsyncMock()
    with pytest.raises(ValueError):
        await calculate_dimension_percentile("dimension_inexistente", 3.0, mock_db)


# ─────────────────────────────────────────────────────────────
# US-6: get_main_weakness (Identificar debilidad principal con desempate)
# ─────────────────────────────────────────────────────────────

def test_get_main_weakness_standard_example():
    # Criterio US-6: {vis: 45, fric: 50, lat: 32, auto: 48, bloq: 40} → "latencia"
    percentiles = {
        "visibilidad": 45,
        "friccion": 50,
        "latencia": 32,
        "auto_cuantificacion": 48,
        "bloqueantes": 40,
    }
    assert get_main_weakness(percentiles) == "latencia"


def test_get_main_weakness_tie_latency_vs_friction():
    # Criterio US-6: Empate latencia=32 y friccion=32 → gana "latencia" por prioridad
    percentiles = {
        "visibilidad": 50,
        "friccion": 32,
        "latencia": 32,
        "auto_cuantificacion": 60,
        "bloqueantes": 40,
    }
    assert get_main_weakness(percentiles) == "latencia"


def test_get_main_weakness_tie_visibility_vs_bloqueantes():
    # Criterio US-6: Empate visibilidad=20 y bloqueantes=20 → gana "visibilidad" (causa raíz #1)
    percentiles = {
        "visibilidad": 20,
        "friccion": 35,
        "latencia": 40,
        "auto_cuantificacion": 50,
        "bloqueantes": 20,
    }
    assert get_main_weakness(percentiles) == "visibilidad"


def test_get_main_weakness_tie_friction_vs_auto_cuantificacion():
    # Criterio US-6: Empate friccion=25 y auto_cuantificacion=25 → gana "friccion"
    percentiles = {
        "visibilidad": 40,
        "friccion": 25,
        "latencia": 30,
        "auto_cuantificacion": 25,
        "bloqueantes": 50,
    }
    assert get_main_weakness(percentiles) == "friccion"


def test_get_main_weakness_all_five_dimensions_tied():
    # Criterio US-6: Empate total quíntuple (todas en 30%) → gana "visibilidad"
    percentiles = {
        "visibilidad": 30,
        "friccion": 30,
        "latencia": 30,
        "auto_cuantificacion": 30,
        "bloqueantes": 30,
    }
    assert get_main_weakness(percentiles) == "visibilidad"


def test_get_main_weakness_ignores_general_key():
    # Asegura que la clave "general" no sea seleccionada aunque tenga menor valor
    percentiles = {
        "visibilidad": 45,
        "friccion": 50,
        "latencia": 32,
        "auto_cuantificacion": 48,
        "bloqueantes": 40,
        "general": 10,
    }
    assert get_main_weakness(percentiles) == "latencia"


def test_get_main_weakness_empty_raises_value_error():
    with pytest.raises(ValueError):
        get_main_weakness({})


# ─────────────────────────────────────────────────────────────
# US-7: calculate_rebalancing_weights (Ponderación Bayesiana)
# ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "total_users, expected_weights",
    [
        (0, (1.0, 0.0)),
        (5, (1.0, 0.0)),
        (10, (1.0, 0.0)),
        (11, (0.8, 0.2)),
        (30, (0.8, 0.2)),
        (50, (0.8, 0.2)),
        (51, (0.6, 0.4)),
        (150, (0.6, 0.4)),  # Criterio US-7: 150 usuarios → (0.6, 0.4)
        (200, (0.6, 0.4)),
        (201, (0.4, 0.6)),
        (350, (0.4, 0.6)),
        (500, (0.4, 0.6)),
        (501, (0.2, 0.8)),
        (1000, (0.2, 0.8)),
    ],
)
def test_calculate_rebalancing_weights_ranges(total_users, expected_weights):
    """Criterio US-7: Verificar cada rango de ponderación según cantidad de usuarios"""
    weights = calculate_rebalancing_weights(total_users)
    assert weights == expected_weights
    # Invariante: la suma de ambos pesos siempre es exactamente 1.0
    assert sum(weights) == pytest.approx(1.0)


def test_calculate_rebalancing_weights_returns_float_tuple():
    """Criterio US-7: Retorna Tuple[float, float]"""
    weights = calculate_rebalancing_weights(150)
    assert isinstance(weights, tuple)
    assert len(weights) == 2
    assert isinstance(weights[0], float)
    assert isinstance(weights[1], float)


def test_calculate_rebalancing_weights_negative_raises_value_error():
    """Manejo de edge case: cantidad negativa de usuarios levanta ValueError"""
    with pytest.raises(ValueError):
        calculate_rebalancing_weights(-1)


# ─────────────────────────────────────────────────────────────
# US-8: generate_benchmark_response (Integration Tests con BD Real)
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_benchmark_response_integration(db: AsyncSession):
    """
    Integration test real (sin mocks) para US-8:
    1. Inserta un UserEvaluation real en la BD.
    2. Ejecuta generate_benchmark_response(evaluation_id, db).
    3. Verifica que retorne una instancia exacta de BenchmarkResponse.
    4. Comprueba que el objeto se serializa a JSON con model_dump_json().
    """
    eval_id = uuid.uuid4()
    test_user = UserEvaluation(
        evaluation_id=eval_id,
        facility_size=FacilitySizeEnum.MEDIUM.value,
        facility_type="colocation",
        region=RegionEnum.LATAM.value,
        # 15 preguntas Likert (1-5)
        p1_visibilidad_herramientas=4,
        p2_visibilidad_dashboards=3,
        p3_visibilidad_telemetry=5,
        p4_friccion_energia=2,
        p5_friccion_cooling=2,
        p6_latencia_manual=3,
        p7_latencia_semi_auto=4,
        p8_latencia_full_auto=3,
        p9_auto_cuant_pue=4,
        p10_auto_cuant_utilizacion=5,
        p11_bloqueantes_staffing=1,
        p12_bloqueantes_supply=2,
        p13_bloqueantes_energy=1,
        p14_bloqueantes_regulacion=2,
        p15_bloqueantes_expertise=1,
    )

    db.add(test_user)
    await db.commit()
    await db.refresh(test_user)

    try:
        # Llamar a la función orquestadora
        response = await generate_benchmark_response(test_user.evaluation_id, db)

        # 1. Verificar tipo exacto
        assert isinstance(response, BenchmarkResponse)

        # 2. Verificar datos de contexto
        assert response.evaluation_id == test_user.evaluation_id
        assert response.user_context.facility_size == FacilitySizeEnum.MEDIUM
        assert response.user_context.region == RegionEnum.LATAM

        # 3. Verificar estructura de scores likert (5 sub-scores float)
        assert isinstance(response.scores_likert.visibilidad, float)
        assert isinstance(response.scores_likert.friccion, float)
        assert isinstance(response.scores_likert.latencia, float)
        assert isinstance(response.scores_likert.auto_cuantificacion, float)
        assert isinstance(response.scores_likert.bloqueantes, float)

        # 4. Verificar estructura de percentiles (int 0-100)
        assert 0 <= response.percentiles.visibilidad <= 100
        assert 0 <= response.percentiles.friccion <= 100
        assert 0 <= response.percentiles.latencia <= 100
        assert 0 <= response.percentiles.auto_cuantificacion <= 100
        assert 0 <= response.percentiles.bloqueantes <= 100
        assert 0 <= response.percentiles.general <= 100

        # 5. Verificar debilidad principal
        assert isinstance(response.main_weakness, (str, MainWeaknessEnriched))
        mw_dim = response.main_weakness.dimension if isinstance(response.main_weakness, MainWeaknessEnriched) else response.main_weakness
        assert mw_dim in [
            "visibilidad",
            "latencia",
            "friccion",
            "auto_cuantificacion",
            "bloqueantes",
        ]


        # 6. Verificar rebalanceo
        assert isinstance(response.rebalancing_status.weight_public, float)
        assert isinstance(response.rebalancing_status.weight_private, float)
        assert response.rebalancing_status.weight_public + response.rebalancing_status.weight_private == pytest.approx(1.0)

        # 7. Verificar serialización JSON completa
        json_output = response.model_dump_json()
        assert isinstance(json_output, str)
        assert len(json_output) > 0
        assert str(test_user.evaluation_id) in json_output
        assert "scores_likert" in json_output
        assert "percentiles" in json_output
        assert "main_weakness" in json_output
        assert "rebalancing_status" in json_output
    finally:
        # Limpieza del registro de prueba
        await db.delete(test_user)
        await db.commit()


@pytest.mark.asyncio
async def test_generate_benchmark_response_not_found_raises_evaluation_not_found_exception(db: AsyncSession):
    """
    Verifica que buscar una evaluación con un UUID inexistente levante EvaluationNotFoundException.
    """
    from app.exceptions import EvaluationNotFoundException

    random_id = uuid.uuid4()
    with pytest.raises(EvaluationNotFoundException) as exc_info:
        await generate_benchmark_response(random_id, db)

    assert str(random_id) in exc_info.value.detail


@pytest.mark.asyncio
async def test_generate_benchmark_response_cached_scores_and_percentiles(db: AsyncSession):
    """
    Verifica que si la evaluación ya tiene scores y percentiles persistidos, se utilicen directamente.
    """
    test_user = UserEvaluation(
        facility_size=FacilitySizeEnum.MEDIUM,
        region=RegionEnum.LATAM,
        p1_visibilidad_herramientas=4,
        p2_visibilidad_dashboards=3,
        p3_visibilidad_telemetry=5,
        p4_friccion_energia=2,
        p5_friccion_cooling=2,
        p6_latencia_manual=3,
        p7_latencia_semi_auto=4,
        p8_latencia_full_auto=3,
        p9_auto_cuant_pue=4,
        p10_auto_cuant_utilizacion=5,
        p11_bloqueantes_staffing=1,
        p12_bloqueantes_supply=2,
        p13_bloqueantes_energy=1,
        p14_bloqueantes_regulacion=2,
        p15_bloqueantes_expertise=1,
        score_visibilidad=4.0,
        score_friccion=2.0,
        score_latencia=3.33,
        score_auto_cuantificacion=4.5,
        score_bloqueantes=1.4,
        percentile_visibilidad=65,
        percentile_friccion=40,
        percentile_latencia=75,
        percentile_auto_cuantificacion=85,
        percentile_bloqueantes=25,
        percentile_general=58,
    )

    db.add(test_user)
    await db.commit()
    await db.refresh(test_user)

    try:
        response = await generate_benchmark_response(test_user.evaluation_id, db)
        assert response.scores_likert.visibilidad == 4.0
        assert response.percentiles.visibilidad == 65
        assert response.percentiles.general == 58
        assert response.main_weakness == "bloqueantes"
    finally:
        await db.delete(test_user)
        await db.commit()



# ─────────────────────────────────────────────────────────────
# normalize_score
# ─────────────────────────────────────────────────────────────

def test_normalize_score_boundaries_and_midpoints():
    """
    Verifica la conversión de escala Likert (1-5) a escala 0-100.
    """
    assert normalize_score(1.0) == 0.0
    assert normalize_score(3.0) == 50.0
    assert normalize_score(5.0) == 100.0
    assert normalize_score(2.0) == 25.0
    assert normalize_score(4.0) == 75.0


# ─────────────────────────────────────────────────────────────
# compute_dimension_scores
# ─────────────────────────────────────────────────────────────

def test_compute_dimension_scores_from_schema():
    """
    Verifica el cálculo de promedios para las 5 dimensiones desde BenchmarkSubmitSchema (p1..p15).
    """
    payload = BenchmarkSubmitSchema(
        facility_size=FacilitySizeEnum.MEDIUM,
        region=RegionEnum.LATAM,
        p1=4,
        p2=3,
        p3=5,
        p4=2,
        p5=2,
        p6=3,
        p7=4,
        p8=3,
        p9=4,
        p10=5,
        p11=1,
        p12=2,
        p13=1,
        p14=2,
        p15=1,
    )
    scores = compute_dimension_scores(payload)
    assert scores["visibilidad"] == 4.0
    assert scores["friccion"] == 2.0
    assert scores["latencia"] == 3.33
    assert scores["auto_cuantificacion"] == 4.5
    assert scores["bloqueantes"] == 1.4


def test_compute_dimension_scores_from_dict_with_long_keys():
    """
    Verifica el cálculo de promedios pasando un diccionario con nombres de campos largos.
    """
    payload_dict = {
        "p1_visibilidad_herramientas": 5,
        "p2_visibilidad_dashboards": 5,
        "p3_visibilidad_telemetry": 5,
        "p4_friccion_energia": 4,
        "p5_friccion_cooling": 4,
        "p6_latencia_manual": 1,
        "p7_latencia_semi_auto": 1,
        "p8_latencia_full_auto": 1,
        "p9_auto_cuant_pue": 3,
        "p10_auto_cuant_utilizacion": 3,
        "p11_bloqueantes_staffing": 2,
        "p12_bloqueantes_supply": 2,
        "p13_bloqueantes_energy": 2,
        "p14_bloqueantes_regulacion": 2,
        "p15_bloqueantes_expertise": 2,
    }
    scores = compute_dimension_scores(payload_dict)
    assert scores["visibilidad"] == 5.0
    assert scores["friccion"] == 4.0
    assert scores["latencia"] == 1.0
    assert scores["auto_cuantificacion"] == 3.0
    assert scores["bloqueantes"] == 2.0


# ─────────────────────────────────────────────────────────────
# compute_percentiles (async)
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_compute_percentiles_iterates_all_dimensions():
    """
    Verifica el cálculo asíncrono de percentiles dimensionales y general.
    """
    mock_db = AsyncMock()
    # Mock público: retorna 1 benchmark con (1, 3, 5) para cada dimensión
    public_result = MagicMock()
    public_result.all.return_value = [(1, 3, 5)]
    # Mock privado: lista vacía
    private_result = MagicMock()
    private_result.all.return_value = []

    mock_db.execute.side_effect = [public_result, private_result] * 5

    scores = {
        "visibilidad": 3.0,
        "friccion": 3.0,
        "latencia": 3.0,
        "auto_cuantificacion": 3.0,
        "bloqueantes": 3.0,
    }
    percentiles = await compute_percentiles(mock_db, scores)

    assert "visibilidad" in percentiles
    assert "friccion" in percentiles
    assert "latencia" in percentiles
    assert "auto_cuantificacion" in percentiles
    assert "bloqueantes" in percentiles
    assert "general" in percentiles
    assert percentiles["general"] == 33


# ─────────────────────────────────────────────────────────────
# identify_main_weakness
# ─────────────────────────────────────────────────────────────

def test_identify_main_weakness_returns_string_or_none():
    scores = {"visibilidad": 4.0, "latencia": 2.0, "friccion": 3.0, "auto_cuantificacion": 4.0, "bloqueantes": 3.0}
    percentiles = {"visibilidad": 80, "latencia": 20, "friccion": 50, "auto_cuantificacion": 85, "bloqueantes": 40}
    assert identify_main_weakness(scores, percentiles) == "latencia"

    # Caso error -> retorna None
    assert identify_main_weakness(scores, {}) is None


# ─────────────────────────────────────────────────────────────
# generate_recommendations
# ─────────────────────────────────────────────────────────────

def test_generate_recommendations_with_low_percentiles():
    scores = {"visibilidad": 2.0, "latencia": 2.0, "friccion": 4.0, "auto_cuantificacion": 4.0, "bloqueantes": 4.0}
    percentiles = {"visibilidad": 30, "latencia": 25, "friccion": 70, "auto_cuantificacion": 80, "bloqueantes": 75, "general": 56}
    recs = generate_recommendations(scores, percentiles)
    assert len(recs) > 0
    assert any("Latencia" in r or "Visibilidad" in r for r in recs)


def test_generate_recommendations_all_high_returns_positive_message():
    scores = {"visibilidad": 4.5, "latencia": 4.5, "friccion": 4.5, "auto_cuantificacion": 4.5, "bloqueantes": 4.5}
    percentiles = {"visibilidad": 90, "latencia": 90, "friccion": 90, "auto_cuantificacion": 90, "bloqueantes": 90, "general": 90}
    recs = generate_recommendations(scores, percentiles)
    assert len(recs) == 1
    assert "Excelente" in recs[0]


# ─────────────────────────────────────────────────────────────
# build_result_response
# ─────────────────────────────────────────────────────────────

def test_build_result_response_constructs_valid_benchmark_response():
    """
    Verifica la transformación de UserEvaluation a BenchmarkResponse oficial.
    """
    eval_mock = UserEvaluation(
        evaluation_id=uuid.uuid4(),
        facility_size=FacilitySizeEnum.LARGE,
        region=RegionEnum.USA,
        facility_type="Enterprise",
        score_visibilidad=4.0,
        score_friccion=3.5,
        score_latencia=2.0,
        score_auto_cuantificacion=4.5,
        score_bloqueantes=1.8,
        percentile_visibilidad=70,
        percentile_friccion=60,
        percentile_latencia=25,
        percentile_auto_cuantificacion=85,
        percentile_bloqueantes=30,
        percentile_general=54,
    )
    response = build_result_response(eval_mock)
    assert isinstance(response, BenchmarkResponse)
    assert response.evaluation_id == eval_mock.evaluation_id
    assert response.main_weakness == "latencia"
    assert response.user_context.facility_size == FacilitySizeEnum.LARGE
    assert response.rebalancing_status.weight_public == 1.0


# ─────────────────────────────────────────────────────────────
# process_evaluation (async)
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_process_evaluation_persists_and_returns_evaluation():
    """
    Verifica que process_evaluation calcule scores/percentiles y persista en BD.
    """
    payload = BenchmarkSubmitSchema(
        facility_size=FacilitySizeEnum.SMALL,
        region=RegionEnum.EUROPE,
        p1=3, p2=3, p3=3, p4=3, p5=3,
        p6=3, p7=3, p8=3, p9=3, p10=3,
        p11=3, p12=3, p13=3, p14=3, p15=3,
    )
    mock_session = AsyncMock()
    # Mock para 5 llamadas a calculate_dimension_percentile (10 queries)
    mock_session.execute.side_effect = [
        MagicMock(all=MagicMock(return_value=[(1, 3, 5)])),
        MagicMock(all=MagicMock(return_value=[])),
    ] * 5

    eval_result = await process_evaluation(mock_session, payload)
    assert eval_result.facility_size == FacilitySizeEnum.SMALL
    assert eval_result.score_visibilidad == 3.0
    assert mock_session.add.called
    assert mock_session.commit.called
    assert mock_session.refresh.called


