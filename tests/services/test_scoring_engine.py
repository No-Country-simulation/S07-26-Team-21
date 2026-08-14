"""
tests/test_scoring_engine.py

Unit tests para app/services/scoring_engine.py (US-4, US-5 y US-6).
Correr con: pytest tests/services/test_scoring_engine.py -v
"""

from unittest.mock import AsyncMock, MagicMock
import pytest

from app.services.scoring_engine import (
    calculate_dimension_percentile,
    calculate_dimension_score,
    get_main_weakness,
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