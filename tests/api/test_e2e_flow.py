import uuid
import pytest
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_evaluation import UserEvaluation


@pytest.mark.asyncio
async def test_e2e_post_submit_valid_payload_returns_201_and_benchmark_response(
    async_client: httpx.AsyncClient, db: AsyncSession
):
    """
    Caso 1: POST /api/v1/benchmark/submit con payload válido devuelve Status 201 Created
    y la respuesta completa del motor con todas sus secciones tipadas.
    """
    valid_payload = {
        "facility_size": "medium",
        "region": "latam",
        "facility_type": "Colocation",
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

    response = await async_client.post("/api/v1/benchmark/submit", json=valid_payload)
    assert response.status_code == 201

    data = response.json()

    # 1. Verificar UUID válido
    eval_id_str = data.get("evaluation_id")
    assert eval_id_str is not None
    eval_uuid = uuid.UUID(eval_id_str)

    # 2. Verificar Contexto de Usuario
    assert data["user_context"]["facility_size"] == "medium"
    assert data["user_context"]["region"] == "latam"

    # 3. Verificar Scores Likert promedio
    scores = data["scores_likert"]
    assert scores["visibilidad"] == 4.0
    assert scores["friccion"] == 2.0
    assert scores["latencia"] == 3.33
    assert scores["auto_cuantificacion"] == 4.5
    assert scores["bloqueantes"] == 1.4

    # 4. Verificar Percentiles (0 a 100)
    percentiles = data["percentiles"]
    for dim in ["visibilidad", "friccion", "latencia", "auto_cuantificacion", "bloqueantes", "general"]:
        assert isinstance(percentiles[dim], int)
        assert 0 <= percentiles[dim] <= 100

    # 5. Verificar Debilidad Principal
    mw_dim = data["main_weakness"]["dimension"] if isinstance(data["main_weakness"], dict) else data["main_weakness"]
    assert mw_dim in ["visibilidad", "friccion", "latencia", "auto_cuantificacion", "bloqueantes"]


    # 6. Verificar Rebalanceo Bayesiano
    rebalancing = data["rebalancing_status"]
    assert isinstance(rebalancing["weight_public"], float)
    assert isinstance(rebalancing["weight_private"], float)
    assert rebalancing["weight_public"] + rebalancing["weight_private"] == pytest.approx(1.0)

    # 7. Limpieza en BD
    eval_db = await db.get(UserEvaluation, eval_uuid)
    if eval_db:
        await db.delete(eval_db)
        await db.commit()


@pytest.mark.asyncio
async def test_e2e_post_submit_invalid_payload_returns_422(async_client: httpx.AsyncClient):
    """
    Caso 2: POST /api/v1/benchmark/submit con payload inválido devuelve Status 422 Unprocessable Entity
    por validación de Pydantic y manejadores de error del backend.
    """
    # 1. Pregunta Likert fuera de rango (p1 = 9)
    invalid_likert_payload = {
        "facility_size": "medium",
        "region": "latam",
        "p1": 9,
        "p2": 3, "p3": 3, "p4": 3, "p5": 3, "p6": 3, "p7": 3, "p8": 3,
        "p9": 3, "p10": 3, "p11": 3, "p12": 3, "p13": 3, "p14": 3, "p15": 3,
    }
    res_likert = await async_client.post("/api/v1/benchmark/submit", json=invalid_likert_payload)
    assert res_likert.status_code == 422
    assert "detail" in res_likert.json()

    # 2. Enum inválido (facility_size = "gigantic")
    invalid_enum_payload = {
        "facility_size": "gigantic",
        "region": "latam",
        "p1": 3, "p2": 3, "p3": 3, "p4": 3, "p5": 3, "p6": 3, "p7": 3, "p8": 3,
        "p9": 3, "p10": 3, "p11": 3, "p12": 3, "p13": 3, "p14": 3, "p15": 3,
    }
    res_enum = await async_client.post("/api/v1/benchmark/submit", json=invalid_enum_payload)
    assert res_enum.status_code == 422
    assert "detail" in res_enum.json()

    # 3. Campo requerido faltante (falta region)
    missing_field_payload = {
        "facility_size": "small",
        "p1": 3, "p2": 3, "p3": 3, "p4": 3, "p5": 3, "p6": 3, "p7": 3, "p8": 3,
        "p9": 3, "p10": 3, "p11": 3, "p12": 3, "p13": 3, "p14": 3, "p15": 3,
    }
    res_missing = await async_client.post("/api/v1/benchmark/submit", json=missing_field_payload)
    assert res_missing.status_code == 422
    assert "detail" in res_missing.json()


@pytest.mark.asyncio
async def test_e2e_consecutive_submissions_differential_percentiles_and_persistence(
    async_client: httpx.AsyncClient, db: AsyncSession
):
    """
    Caso 3: Dos envíos sucesivos con datos de usuarios diferentes demuestran la correcta
    persistencia en base de datos y el cálculo de percentiles y debilidades diferenciales.
    """
    # Usuario A: Data Center Avanzado pero con Latencia de Coordinación Crítica
    elite_payload = {
        "facility_size": "large",
        "region": "usa",
        "facility_type": "Hyperscale",
        "p1": 5, "p2": 5, "p3": 5,  # visibilidad = 5.0 (pct 67)
        "p4": 5, "p5": 5,            # friccion = 5.0 (pct 67)
        "p6": 2, "p7": 2, "p8": 2,  # latencia = 2.0 (pct 33 - debilidad principal)
        "p9": 5, "p10": 5,           # auto_cuant = 5.0 (pct 67)
        "p11": 5, "p12": 5, "p13": 5, "p14": 5, "p15": 5,  # bloqueantes = 5.0 (pct 67)
    }

    # Usuario B: Data Center con Fricción Operativa Crítica (Outages / Cooling)
    lagging_payload = {
        "facility_size": "small",
        "region": "latam",
        "facility_type": "Edge",
        "p1": 3, "p2": 3, "p3": 3,  # visibilidad = 3.0 (pct 33)
        "p4": 1, "p5": 1,            # friccion = 1.0 (pct 0 - debilidad principal)
        "p6": 3, "p7": 3, "p8": 3,  # latencia = 3.0 (pct 33)
        "p9": 3, "p10": 3,           # auto_cuant = 3.0 (pct 33)
        "p11": 3, "p12": 3, "p13": 3, "p14": 3, "p15": 3,  # bloqueantes = 3.0 (pct 33)
    }

    res_a = await async_client.post("/api/v1/benchmark/submit", json=elite_payload)
    res_b = await async_client.post("/api/v1/benchmark/submit", json=lagging_payload)

    assert res_a.status_code == 201
    assert res_b.status_code == 201

    data_a = res_a.json()
    data_b = res_b.json()

    id_a = uuid.UUID(data_a["evaluation_id"])
    id_b = uuid.UUID(data_b["evaluation_id"])

    eval_a_db = None
    eval_b_db = None

    try:
        # Verificar que tienen IDs únicos
        assert id_a != id_b

        # Verificar persistencia en base de datos PostgreSQL
        eval_a_db = await db.get(UserEvaluation, id_a)
        eval_b_db = await db.get(UserEvaluation, id_b)
        assert eval_a_db is not None
        assert eval_b_db is not None

        # Verificar diferenciación de scores Likert
        assert data_a["scores_likert"]["visibilidad"] > data_b["scores_likert"]["visibilidad"]
        assert data_a["scores_likert"]["friccion"] > data_b["scores_likert"]["friccion"]

        # Verificar cálculo diferencial de percentiles generales y por dimensión
        assert data_a["percentiles"]["general"] > data_b["percentiles"]["general"]
        assert data_a["percentiles"]["visibilidad"] > data_b["percentiles"]["visibilidad"]
        assert data_a["percentiles"]["friccion"] > data_b["percentiles"]["friccion"]

        # Verificar debilidad principal calculada acorde a su perfil
        mw_a = data_a["main_weakness"]["dimension"] if isinstance(data_a["main_weakness"], dict) else data_a["main_weakness"]
        mw_b = data_b["main_weakness"]["dimension"] if isinstance(data_b["main_weakness"], dict) else data_b["main_weakness"]
        assert mw_a == "latencia"
        assert mw_b == "friccion"




    finally:
        # Limpieza de registros de prueba
        if eval_a_db:
            await db.delete(eval_a_db)
        if eval_b_db:
            await db.delete(eval_b_db)
        await db.commit()
