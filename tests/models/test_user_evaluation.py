import uuid
from datetime import date
from sqlalchemy import CheckConstraint
from app.core.database import Base
from app.models.user_evaluation import UserEvaluation


def test_import_user_evaluation():
    """Criterio: Se puede importar from app.models.user_evaluation import UserEvaluation"""
    from app.models.user_evaluation import UserEvaluation as ImportedModel

    assert ImportedModel is UserEvaluation


def test_user_evaluation_inherits_from_base():
    """Criterio: Clase UserEvaluation hereda de Base"""
    assert issubclass(UserEvaluation, Base)
    assert UserEvaluation.__tablename__ == "user_evaluations"


def test_evaluation_id_is_uuid_primary_key():
    """Criterio: Campo evaluation_id es UUID Primary Key"""
    table = UserEvaluation.__table__
    col = table.columns["evaluation_id"]

    assert col.primary_key is True
    assert "UUID" in str(col.type).upper()


def test_context_and_likert_columns_exist():
    """Criterio: Campos facility_size, region y p1 a p15 existen y son requeridos"""
    table = UserEvaluation.__table__

    # Contexto
    assert table.columns["facility_size"].nullable is False
    assert table.columns["region"].nullable is False
    assert table.columns["facility_type"].nullable is True or table.columns["facility_type"].default is not None

    # Fecha
    assert table.columns["created_at"].nullable is False

    # 15 Preguntas Likert
    expected_questions = [
        "p1_visibilidad_herramientas",
        "p2_visibilidad_dashboards",
        "p3_visibilidad_telemetry",
        "p4_friccion_energia",
        "p5_friccion_cooling",
        "p6_latencia_manual",
        "p7_latencia_semi_auto",
        "p8_latencia_full_auto",
        "p9_auto_cuant_pue",
        "p10_auto_cuant_utilizacion",
        "p11_bloqueantes_staffing",
        "p12_bloqueantes_supply",
        "p13_bloqueantes_energy",
        "p14_bloqueantes_regulacion",
        "p15_bloqueantes_expertise",
    ]

    for q in expected_questions:
        assert q in table.columns, f"Columna {q} no encontrada en la tabla user_evaluations"
        assert table.columns[q].nullable is False


def test_check_constraints_defined():
    """Criterio: Campos facility_size, region y p1 a p15 tienen CheckConstraints (1-5 y valores válidos)"""
    table = UserEvaluation.__table__
    constraints = [c for c in table.constraints if isinstance(c, CheckConstraint)]
    constraint_names = {c.name for c in constraints}

    # Constraints de contexto
    assert "ck_user_evaluations_facility_size" in constraint_names
    assert "ck_user_evaluations_region" in constraint_names

    # Constraints Likert (ck_p1_range .. ck_p15_range)
    for i in range(1, 16):
        assert f"ck_p{i}_range" in constraint_names, f"Constraint ck_p{i}_range no encontrado"


def test_instance_instantiation_and_repr():
    """Verifica instanciación correcta de un objeto UserEvaluation y método __repr__"""
    eval_id = uuid.uuid4()
    today = date.today()

    instance = UserEvaluation(
        evaluation_id=eval_id,
        facility_size="medium",
        facility_type="Enterprise",
        region="latam",
        created_at=today,
        p1_visibilidad_herramientas=4,
        p2_visibilidad_dashboards=3,
        p3_visibilidad_telemetry=5,
        p4_friccion_energia=2,
        p5_friccion_cooling=3,
        p6_latencia_manual=1,
        p7_latencia_semi_auto=4,
        p8_latencia_full_auto=4,
        p9_auto_cuant_pue=5,
        p10_auto_cuant_utilizacion=3,
        p11_bloqueantes_staffing=2,
        p12_bloqueantes_supply=1,
        p13_bloqueantes_energy=4,
        p14_bloqueantes_regulacion=3,
        p15_bloqueantes_expertise=5,
    )

    assert instance.evaluation_id == eval_id
    assert instance.facility_size == "medium"
    assert instance.region == "latam"
    assert instance.p1_visibilidad_herramientas == 4
    assert str(eval_id) in repr(instance)
