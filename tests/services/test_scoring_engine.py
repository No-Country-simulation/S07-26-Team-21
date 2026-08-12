"""
tests/test_scoring_engine.py

Unit tests para app/services/scoring_engine.py (US-4).
Correr con: pytest tests/test_scoring_engine.py -v
"""

import pytest

from app.services.scoring_engine import calculate_dimension_score


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