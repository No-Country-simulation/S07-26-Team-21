import json
import uuid
import pytest
from pydantic import ValidationError
from app.schemas.benchmark_input import FacilitySizeEnum, RegionEnum
from app.schemas.benchmark_output import (
    BenchmarkResponse,
    BenchmarkResultSchema,
    PercentilesResponse,
    RebalancingStatusResponse,
    ScoresLikertResponse,
    UserContextResponse,
)


@pytest.fixture
def valid_benchmark_response_payload():
    return {
        "evaluation_id": "123e4567-e89b-12d3-a456-426614174000",
        "user_context": {
            "facility_size": "medium",
            "region": "latam",
        },
        "scores_likert": {
            "visibilidad": 3.67,
            "friccion": 2.50,
            "latencia": 4.00,
            "auto_cuantificacion": 3.00,
            "bloqueantes": 2.20,
        },
        "percentiles": {
            "visibilidad": 65,
            "friccion": 42,
            "latencia": 80,
            "auto_cuantificacion": 55,
            "bloqueantes": 38,
            "general": 60,
        },
        "main_weakness": "friccion",
        "rebalancing_status": {
            "weight_public": 0.85,
            "weight_private": 0.15,
        },
    }


def test_import_benchmark_response():
    """Criterio: Se puede importar from app.schemas.benchmark_output import BenchmarkResponse"""
    from app.schemas.benchmark_output import BenchmarkResponse as ImportedSchema

    assert ImportedSchema is BenchmarkResponse
    assert BenchmarkResultSchema is BenchmarkResponse


def test_valid_benchmark_response_structure(valid_benchmark_response_payload):
    """Criterio: Estructura tiene 6 secciones con los tipos correctos"""
    schema = BenchmarkResponse(**valid_benchmark_response_payload)

    # 1. evaluation_id (UUID)
    assert isinstance(schema.evaluation_id, uuid.UUID)
    assert str(schema.evaluation_id) == "123e4567-e89b-12d3-a456-426614174000"

    # 2. user_context
    assert isinstance(schema.user_context, UserContextResponse)
    assert schema.user_context.facility_size == FacilitySizeEnum.MEDIUM
    assert schema.user_context.region == RegionEnum.LATAM

    # 3. scores_likert (float)
    assert isinstance(schema.scores_likert, ScoresLikertResponse)
    assert isinstance(schema.scores_likert.visibilidad, float)
    assert schema.scores_likert.visibilidad == 3.67
    assert schema.scores_likert.bloqueantes == 2.20

    # 4. percentiles (int)
    assert isinstance(schema.percentiles, PercentilesResponse)
    assert isinstance(schema.percentiles.visibilidad, int)
    assert schema.percentiles.visibilidad == 65
    assert schema.percentiles.general == 60

    # 5. main_weakness (str)
    assert isinstance(schema.main_weakness, str)
    assert schema.main_weakness == "friccion"

    # 6. rebalancing_status (float)
    assert isinstance(schema.rebalancing_status, RebalancingStatusResponse)
    assert isinstance(schema.rebalancing_status.weight_public, float)
    assert schema.rebalancing_status.weight_public == 0.85
    assert schema.rebalancing_status.weight_private == 0.15


def test_json_serialization_without_errors(valid_benchmark_response_payload):
    """Criterio: Se puede serializar a JSON sin errores"""
    schema = BenchmarkResponse(**valid_benchmark_response_payload)

    # Serialización a string JSON
    json_str = schema.model_dump_json()
    assert isinstance(json_str, str)

    # Deserialización y verificación de campos
    data = json.loads(json_str)
    assert data["evaluation_id"] == "123e4567-e89b-12d3-a456-426614174000"
    assert data["user_context"]["facility_size"] == "medium"
    assert data["user_context"]["region"] == "latam"
    assert data["scores_likert"]["visibilidad"] == 3.67
    assert data["percentiles"]["general"] == 60
    assert data["main_weakness"] == "friccion"
    assert data["rebalancing_status"]["weight_public"] == 0.85


@pytest.mark.parametrize(
    "required_section",
    [
        "evaluation_id",
        "user_context",
        "scores_likert",
        "percentiles",
        "main_weakness",
        "rebalancing_status",
    ],
)
def test_missing_required_section_raises_validation_error(
    valid_benchmark_response_payload, required_section
):
    """Criterio: Faltar cualquiera de las 6 secciones levanta ValidationError"""
    del valid_benchmark_response_payload[required_section]
    with pytest.raises(ValidationError) as exc_info:
        BenchmarkResponse(**valid_benchmark_response_payload)

    errors = exc_info.value.errors()
    assert any(e["loc"] == (required_section,) for e in errors)


def test_invalid_uuid_raises_validation_error(valid_benchmark_response_payload):
    """Criterio: evaluation_id debe ser un UUID válido"""
    valid_benchmark_response_payload["evaluation_id"] = "not-a-valid-uuid"
    with pytest.raises(ValidationError):
        BenchmarkResponse(**valid_benchmark_response_payload)


def test_invalid_user_context_enum(valid_benchmark_response_payload):
    """Criterio: user_context valida enums correctamente"""
    valid_benchmark_response_payload["user_context"]["facility_size"] = "invalid_size"
    with pytest.raises(ValidationError):
        BenchmarkResponse(**valid_benchmark_response_payload)


def test_invalid_scores_type(valid_benchmark_response_payload):
    """Criterio: scores_likert debe contener números float"""
    valid_benchmark_response_payload["scores_likert"]["visibilidad"] = "not_a_number"
    with pytest.raises(ValidationError):
        BenchmarkResponse(**valid_benchmark_response_payload)


def test_invalid_percentiles_type(valid_benchmark_response_payload):
    """Criterio: percentiles debe contener enteros"""
    valid_benchmark_response_payload["percentiles"]["visibilidad"] = "not_an_int"
    with pytest.raises(ValidationError):
        BenchmarkResponse(**valid_benchmark_response_payload)
