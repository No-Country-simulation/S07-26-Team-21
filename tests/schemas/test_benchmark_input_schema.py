import pytest
from pydantic import ValidationError
from app.schemas.benchmark_input import (
    BenchmarkRequest,
    BenchmarkSubmitSchema,
    FacilitySizeEnum,
    RegionEnum,
)


@pytest.fixture
def valid_benchmark_payload():
    return {
        "facility_size": "medium",
        "region": "latam",
        "facility_type": "Enterprise",
        "p1": 4,
        "p2": 3,
        "p3": 5,
        "p4": 2,
        "p5": 3,
        "p6": 1,
        "p7": 4,
        "p8": 4,
        "p9": 5,
        "p10": 3,
        "p11": 2,
        "p12": 1,
        "p13": 4,
        "p14": 3,
        "p15": 5,
    }


def test_import_benchmark_request():
    """Criterio: Se puede importar from app.schemas.benchmark_input import BenchmarkRequest"""
    from app.schemas.benchmark_input import BenchmarkRequest as ImportedSchema

    assert ImportedSchema is BenchmarkRequest
    assert BenchmarkSubmitSchema is BenchmarkRequest


def test_valid_payload(valid_benchmark_payload):
    """Criterio: Un payload válido se instancia correctamente con los tipos esperados"""
    schema = BenchmarkRequest(**valid_benchmark_payload)

    assert schema.facility_size == FacilitySizeEnum.MEDIUM
    assert schema.region == RegionEnum.LATAM
    assert schema.facility_type == "Enterprise"
    assert schema.p1 == 4
    assert schema.p15 == 5


@pytest.mark.parametrize("valid_size", ["small", "medium", "large", "mega"])
def test_valid_facility_sizes(valid_benchmark_payload, valid_size):
    """Criterio: facility_size acepta los 4 valores del enum"""
    valid_benchmark_payload["facility_size"] = valid_size
    schema = BenchmarkRequest(**valid_benchmark_payload)
    assert schema.facility_size == valid_size


@pytest.mark.parametrize("invalid_size", ["mediano", "huge", "tiny", "", 123])
def test_invalid_facility_sizes(valid_benchmark_payload, invalid_size):
    """Criterio: facility_size rechaza valores fuera del enum"""
    valid_benchmark_payload["facility_size"] = invalid_size
    with pytest.raises(ValidationError) as exc_info:
        BenchmarkRequest(**valid_benchmark_payload)

    errors = exc_info.value.errors()
    assert any(e["loc"] == ("facility_size",) for e in errors)


@pytest.mark.parametrize("valid_region", ["latam", "usa", "europe", "apac"])
def test_valid_regions(valid_benchmark_payload, valid_region):
    """Criterio: region acepta los 4 valores del enum"""
    valid_benchmark_payload["region"] = valid_region
    schema = BenchmarkRequest(**valid_benchmark_payload)
    assert schema.region == valid_region


@pytest.mark.parametrize("invalid_region", ["asia", "argentina", "global", "", 123])
def test_invalid_regions(valid_benchmark_payload, invalid_region):
    """Criterio: region rechaza valores fuera del enum"""
    valid_benchmark_payload["region"] = invalid_region
    with pytest.raises(ValidationError) as exc_info:
        BenchmarkRequest(**valid_benchmark_payload)

    errors = exc_info.value.errors()
    assert any(e["loc"] == ("region",) for e in errors)


@pytest.mark.parametrize("question_key", [f"p{i}" for i in range(1, 16)])
@pytest.mark.parametrize("invalid_score", [0, -1, 6, 10, "invalid_str"])
def test_likert_questions_range_validation(valid_benchmark_payload, question_key, invalid_score):
    """Criterio: Campos p1 a p15 son INT, rango [1,5] estricto"""
    valid_benchmark_payload[question_key] = invalid_score
    with pytest.raises(ValidationError) as exc_info:
        BenchmarkRequest(**valid_benchmark_payload)

    errors = exc_info.value.errors()
    assert any(e["loc"] == (question_key,) for e in errors)


@pytest.mark.parametrize("question_key", [f"p{i}" for i in range(1, 16)])
def test_likert_questions_cannot_be_none_or_missing(valid_benchmark_payload, question_key):
    """Criterio: Campos p1 a p15 son no nulos y requeridos"""
    # Test None
    payload_with_none = valid_benchmark_payload.copy()
    payload_with_none[question_key] = None
    with pytest.raises(ValidationError):
        BenchmarkRequest(**payload_with_none)

    # Test Missing
    payload_missing = valid_benchmark_payload.copy()
    del payload_missing[question_key]
    with pytest.raises(ValidationError):
        BenchmarkRequest(**payload_missing)


def test_missing_required_metadata(valid_benchmark_payload):
    """Criterio: facility_size y region son obligatorios"""
    del valid_benchmark_payload["facility_size"]
    with pytest.raises(ValidationError) as exc_info:
        BenchmarkRequest(**valid_benchmark_payload)

    errors = exc_info.value.errors()
    assert any(e["loc"] == ("facility_size",) for e in errors)
