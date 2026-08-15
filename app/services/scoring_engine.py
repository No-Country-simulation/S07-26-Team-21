"""
Motor de Scoring – BENCHMARK·DC Engine
=======================================
Calcula scores por dimensión, percentiles count-based relativos a la industria,
identifica la debilidad principal con jerarquía de causa raíz y calcula el
rebalanceo dinámico bayesiano.

Arquitectura y Componentes:
    - calculate_dimension_score()    → US-4: Promedio aritmético puro Likert (1.0 – 5.0).
    - calculate_dimension_percentile()→ US-5: Percentil count-based combinando 105 niveles
                                      públicos + evaluaciones privadas de la BD.
    - get_main_weakness()            → US-6: Dimensión con menor percentil con desempate
                                      (visibilidad > latencia > friccion > auto_cuant > bloqueantes).
    - calculate_rebalancing_weights()→ US-7: Ponderación de pesos dataset público vs privado.
    - generate_benchmark_response()  → US-8: Orquestador asíncrono completo que genera
                                      el BenchmarkResponse (US-2) tipado.
"""

from typing import List
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import EvaluationNotFoundException
from app.models.industry_benchmark import IndustryBenchmark
from app.models.user_evaluation import UserEvaluation

from app.schemas.benchmark_input import BenchmarkSubmitSchema
from app.schemas.benchmark_output import (
    BenchmarkResponse,
    BenchmarkResultSchema,
    PercentilesResponse,
    RebalancingStatusResponse,
    ScoresLikertResponse,
    UserContextResponse,
)



# ─────────────────────────────────────────────────────────────
# Constantes: Mapeo de Dimensiones → Preguntas Likert
# ─────────────────────────────────────────────────────────────

DIMENSION_QUESTIONS: dict[str, list[str]] = {
    "visibilidad": [
        "p1_visibilidad_herramientas",
        "p2_visibilidad_dashboards",
        "p3_visibilidad_telemetry",
    ],
    "friccion": [
        "p4_friccion_energia",
        "p5_friccion_cooling",
    ],
    "latencia": [
        "p6_latencia_manual",
        "p7_latencia_semi_auto",
        "p8_latencia_full_auto",
    ],
    "auto_cuantificacion": [
        "p9_auto_cuant_pue",
        "p10_auto_cuant_utilizacion",
    ],
    "bloqueantes": [
        "p11_bloqueantes_staffing",
        "p12_bloqueantes_supply",
        "p13_bloqueantes_energy",
        "p14_bloqueantes_regulacion",
        "p15_bloqueantes_expertise",
    ],
}

DIMENSION_LABELS: dict[str, str] = {
    "visibilidad": "Visibilidad Cross-Layer",
    "friccion": "Atribución de Fricción",
    "latencia": "Latencia de Coordinación",
    "auto_cuantificacion": "Auto-Cuantificación",
    "bloqueantes": "Bloqueantes",
}

# Mapeo dimensión → columna ORM de score (para queries de percentil)
SCORE_COLUMNS: dict[str, any] = {
    "visibilidad": UserEvaluation.score_visibilidad,
    "friccion": UserEvaluation.score_friccion,
    "latencia": UserEvaluation.score_latencia,
    "auto_cuantificacion": UserEvaluation.score_auto_cuantificacion,
    "bloqueantes": UserEvaluation.score_bloqueantes,
}

# ─────────────────────────────────────────────────────────────
# US-4: Función pura de promedio (sin acceso a BD)
# ─────────────────────────────────────────────────────────────
 
def calculate_dimension_score(p_list: List[int]) -> float:
    """
    Calcula el sub-score de una dimensión como el promedio aritmético
    de sus preguntas Likert asociadas.
 
    Función pura: no accede a la base de datos ni a ningún schema.
    Por eso es 100% testeable de forma aislada
    (ver tests/test_scoring_engine.py).
 
    Args:
        p_list: Respuestas Likert (enteros entre 1 y 5) de UNA dimensión.
 
    Returns:
        Promedio aritmético como float, en el rango [1.0, 5.0].
 
    Raises:
        ValueError: si `p_list` está vacía.
 
    Ejemplo:
        >>> calculate_dimension_score([3, 2, 4])
        3.0
        >>> calculate_dimension_score([1, 1, 1])
        1.0
        >>> calculate_dimension_score([5, 5, 5])
        5.0
    """
    if not p_list:
        raise ValueError("p_list no puede estar vacía: no hay nada que promediar.")
 
    return sum(p_list) / len(p_list)

# ─────────────────────────────────────────────────────────────
# 1. Calcular Scores Likert por Dimensión
# ─────────────────────────────────────────────────────────────

def compute_dimension_scores(data: BenchmarkSubmitSchema) -> dict[str, float]:
    """
    Calcula el promedio Likert (1.0 – 5.0) de cada dimensión.

    Ejemplo:
        Si p1=4, p2=3, p3=5 → visibilidad = (4+3+5)/3 = 4.0
    """
    data_dict = data.model_dump()
    scores: dict[str, float] = {}

    for dimension, questions in DIMENSION_QUESTIONS.items():
        values = [data_dict[q] for q in questions]
        scores[dimension] = round(calculate_dimension_score(values), 2)

    return scores


# ─────────────────────────────────────────────────────────────
# 2. Normalizar Score Likert a Escala 0-100
# ─────────────────────────────────────────────────────────────

def normalize_score(likert_avg: float) -> float:
    """
    Convierte un promedio Likert (1–5) a una escala de 0 a 100.

    Fórmula: ((valor - 1) / 4) × 100
        - Likert 1.0 → 0.0
        - Likert 3.0 → 50.0
        - Likert 5.0 → 100.0
    """
    return round(((likert_avg - 1) / 4) * 100, 1)


# ─────────────────────────────────────────────────────────────
# US-5: Percentil Count-Based de UNA dimensión (públicos + privados)
# ─────────────────────────────────────────────────────────────
 
def _percentile_from_scores(user_score: float, all_scores: list[float]) -> int:
    """
    Calcula el percentil de `user_score` dentro de una lista combinada de scores de referencia (benchmarks públicos + evaluaciones privadas), usando el algoritmo count-based:
 
        Percentil = (cantidad de scores < user_score / total) × 100
 
    Función pura: no accede a la base de datos. Se separó para poder testear el algoritmo de percentil sin tener que mockear una
    sesión async — mismo patrón que calculate_dimension_score en la US-4 (una función pura y testeada, con la función async delegando en ella).
 
    Args:
        user_score: score Likert (1.0-5.0) de la evaluación a ubicar.
        all_scores: todos los scores de referencia (públicos + privados) de esa dimensión.
 
    Returns:
        Percentil entero en [0, 100]. Si `all_scores` está vacía,
        retorna 50 (posición media por defecto — edge case sin datos).
 
    Ejemplo:
        >>> _percentile_from_scores(3, [1, 1, 1, 3, 3, 3, 5, 5, 5])
        33
    """
    total = len(all_scores)
    if total == 0:
        return 50
 
    lower_count = sum(1 for score in all_scores if score < user_score)
    return round((lower_count / total) * 100)
 
 
async def calculate_dimension_percentile(
    dimension: str,
    user_score: float,
    db: AsyncSession,
) -> int:
    """
    Calcula el percentil de un score de usuario dentro de UNA dimensión,
    comparándolo contra:
        1. Los benchmarks públicos de industry_benchmarks para esa
           dimensión (niveles Likert 1, 3 y 5 de cada fuente).
        2. Los scores privados de evaluaciones previas de otros
           usuarios en user_evaluations.
 
    El cálculo del percentil en sí (contar + dividir) se delega en
    _percentile_from_scores(), que es pura y está testeada aparte.
 
    Args:
        dimension: clave de la dimensión ("visibilidad", "friccion",
            "latencia", "auto_cuantificacion" o "bloqueantes").
        user_score: score Likert promedio (1.0-5.0) del usuario en
            esa dimensión.
        db: sesión async de SQLAlchemy.
 
    Returns:
        Percentil entero en [0, 100]. Si no hay ningún score de
        referencia (ni público ni privado), retorna 50 por defecto.
 
    Raises:
        ValueError: si `dimension` no es una clave válida.
 
    Ejemplo:
        Con 35 benchmarks públicos (1,3,5 por fuente) y 1 evaluación
        privada previa en 2.67 para "latencia", un usuario con
        score 2.67 en esa dimensión obtiene ~32% de percentil.
    """
    if dimension not in SCORE_COLUMNS:
        raise ValueError(f"Dimensión desconocida: {dimension!r}")
 
    # 1. Benchmarks públicos: 3 niveles Likert por cada fuente de la dimensión
    public_result = await db.execute(
        select(
            IndustryBenchmark.level_1_likert_equivalent,
            IndustryBenchmark.level_3_likert_equivalent,
            IndustryBenchmark.level_5_likert_equivalent,
        ).where(IndustryBenchmark.dimension == dimension)
    )
    public_scores: list[float] = [
        level for row in public_result.all() for level in row
    ]
 
    # 2. Scores privados: evaluaciones previas de usuarios reales
    score_col = SCORE_COLUMNS[dimension]
    private_result = await db.execute(
        select(score_col).where(score_col.isnot(None))
    )
    private_scores: list[float] = [row[0] for row in private_result.all()]
 
    # 3-5. Combinar públicos + privados y calcular percentil
    return _percentile_from_scores(user_score, public_scores + private_scores)
 



# ─────────────────────────────────────────────────────────────
# 3. Calcular Percentiles vs. Evaluaciones Previas
# ─────────────────────────────────────────────────────────────

async def compute_percentiles(
    session: AsyncSession,
    scores: dict[str, float],
) -> dict[str, int]:
    """
    Calcula los percentiles para las 5 dimensiones y el percentil general,
    combinando benchmarks públicos de la industria y evaluaciones privadas
    mediante `calculate_dimension_percentile` (US-5).
    """
    percentiles: dict[str, int] = {}
    for dim in DIMENSION_QUESTIONS:
        user_score = scores.get(dim, 3.0)
        percentiles[dim] = await calculate_dimension_percentile(dim, user_score, session)

    avg_percentile = sum(percentiles.values()) / len(percentiles)
    percentiles["general"] = round(avg_percentile)
    return percentiles



# ─────────────────────────────────────────────────────────────
# US-6 / Sección 4: Identificar la Debilidad Principal con Prioridad
# ─────────────────────────────────────────────────────────────

WEAKNESS_PRIORITY_ORDER: list[str] = [
    "visibilidad",
    "latencia",
    "friccion",
    "auto_cuantificacion",
    "bloqueantes",
]


def get_main_weakness(dimension_percentiles: dict[str, int]) -> str:
    """
    Calcula la dimensión con el percentil más bajo (mayor oportunidad de mejora).

    Si hay empate, aplica el orden de prioridad de causa raíz:
        visibilidad > latencia > friccion > auto_cuantificacion > bloqueantes

    Args:
        dimension_percentiles: Diccionario con los percentiles por dimensión.

    Returns:
        Nombre de la dimensión más débil (ej: 'latencia', 'visibilidad').

    Raises:
        ValueError: si no se proporcionan dimensiones válidas.

    Ejemplo:
        >>> get_main_weakness({"visibilidad": 45, "friccion": 50, "latencia": 32, "auto_cuantificacion": 48, "bloqueantes": 40})
        'latencia'
    """
    # Filtrar solo dimensiones válidas (excluir 'general' y claves ajenas)
    valid_dims = {
        dim: dimension_percentiles[dim]
        for dim in WEAKNESS_PRIORITY_ORDER
        if dim in dimension_percentiles
    }

    if not valid_dims:
        raise ValueError(
            "dimension_percentiles no contiene dimensiones válidas."
        )

    # 1. Obtener el percentil mínimo
    min_val = min(valid_dims.values())

    # 2. Identificar candidatos empatados en el mínimo
    tied_dims = {dim for dim, val in valid_dims.items() if val == min_val}

    # 3. Retornar el de mayor prioridad según la jerarquía de causa raíz
    for dim in WEAKNESS_PRIORITY_ORDER:
        if dim in tied_dims:
            return dim

    return next(iter(tied_dims))


def identify_main_weakness(
    scores: dict[str, float],
    percentiles: dict[str, int],
) -> str | None:
    """
    Retorna el nombre de la dimensión con el percentil más bajo, como
    string simple (alineado con BenchmarkResponse.main_weakness, US-2 y US-6).
    """
    try:
        return get_main_weakness(percentiles)
    except ValueError:
        return None


# ─────────────────────────────────────────────────────────────
# 5. Generar Recomendaciones Priorizadas
# ─────────────────────────────────────────────────────────────

RECOMMENDATIONS_MAP: dict[str, list[str]] = {
    "visibilidad": [
        "Implementar un dashboard unificado que integre métricas de energía, cooling e IT en tiempo real.",
        "Adoptar telemetría cross-layer con rastreo de Scope 1-2-3 para emisiones.",
        "Considerar herramientas de monitoreo DCIM (Data Center Infrastructure Management).",
    ],
    "friccion": [
        "Realizar un análisis de causa raíz de outages recientes para identificar puntos de fricción.",
        "Implementar redundancia N+1 en sistemas de energía y cooling.",
        "Automatizar la coordinación entre sistemas de energía y refrigeración.",
    ],
    "latencia": [
        "Migrar de procesos manuales a semi-automatizados para la respuesta a cambios de carga.",
        "Evaluar soluciones de orquestación automatizada (ej. Kubernetes, auto-scaling).",
        "Reducir el tiempo de provisioning implementando infraestructura como código.",
    ],
    "auto_cuantificacion": [
        "Implementar medición continua del PUE y comparar con el benchmark de la industria (PUE 1.56 promedio mundial).",
        "Establecer dashboards de utilización de servidores para identificar stranded capacity.",
        "Cuantificar la capacidad desperdiciada en términos de costo operativo mensual.",
    ],
    "bloqueantes": [
        "Desarrollar un plan de capacitación para reducir la brecha de expertise técnico.",
        "Diversificar la cadena de suministro para reducir dependencia de proveedores únicos.",
        "Evaluar fuentes de energía renovable para reducir bloqueantes regulatorios y de costos.",
    ],
}


def generate_recommendations(
    scores: dict[str, float],
    percentiles: dict[str, int],
) -> list[str]:
    """
    Genera recomendaciones priorizadas según las dimensiones más débiles.

    Criterio: se incluyen recomendaciones para dimensiones con
    percentil < 50 o score Likert < 3.0 (por debajo del promedio).

    Las dimensiones se ordenan de peor a mejor para priorizar.
    """
    recommendations: list[str] = []

    # Ordenar dimensiones por percentil ascendente (peores primero)
    dim_percentiles = {
        k: v for k, v in percentiles.items() if k != "general"
    }
    sorted_dims = sorted(dim_percentiles, key=dim_percentiles.get)

    for dim in sorted_dims:
        pct = dim_percentiles[dim]
        score = scores.get(dim, 3.0)

        # Solo recomendar si el percentil es bajo o el score es malo
        if pct < 50 or score < 3.0:
            dim_recs = RECOMMENDATIONS_MAP.get(dim, [])
            label = DIMENSION_LABELS.get(dim, dim)
            # Máximo 2 recomendaciones por dimensión para no saturar
            for rec in dim_recs[:2]:
                recommendations.append(f"[{label}] {rec}")

    # Si todo está por encima del promedio, dar mensaje positivo
    if not recommendations:
        recommendations.append(
            "¡Excelente! Su centro de datos muestra un nivel de madurez operativa "
            "superior al promedio de la industria. Continúe monitoreando sus métricas "
            "para mantener su posición competitiva."
        )

    return recommendations


# ─────────────────────────────────────────────────────────────
# 6. Función Principal: Procesar Evaluación Completa
# ─────────────────────────────────────────────────────────────

async def process_evaluation(
    session: AsyncSession,
    data: BenchmarkSubmitSchema,
) -> UserEvaluation:
    """
    Orquesta todo el flujo de scoring:
        1. Calcula scores Likert promedio por dimensión
        2. Calcula percentiles contra evaluaciones previas
        3. Crea y persiste el registro de evaluación con todos los cálculos

    NOTA: Los percentiles se calculan ANTES de insertar la nueva evaluación
    para evitar sesgo de auto-comparación.

    Retorna el objeto UserEvaluation ya persistido en la BD.
    """
    # Paso 1: Calcular scores promedio por dimensión
    scores = compute_dimension_scores(data)

    # Paso 2: Calcular percentiles (antes de insertar para no comparar consigo misma)
    percentiles = await compute_percentiles(session, scores)

    # Paso 3: Crear el registro completo de evaluación
    evaluation = UserEvaluation(
        # Contexto del data center
        facility_size=data.facility_size,
        facility_type=data.facility_type,
        region=data.region,
        # 15 respuestas Likert originales
        p1_visibilidad_herramientas=data.p1_visibilidad_herramientas,
        p2_visibilidad_dashboards=data.p2_visibilidad_dashboards,
        p3_visibilidad_telemetry=data.p3_visibilidad_telemetry,
        p4_friccion_energia=data.p4_friccion_energia,
        p5_friccion_cooling=data.p5_friccion_cooling,
        p6_latencia_manual=data.p6_latencia_manual,
        p7_latencia_semi_auto=data.p7_latencia_semi_auto,
        p8_latencia_full_auto=data.p8_latencia_full_auto,
        p9_auto_cuant_pue=data.p9_auto_cuant_pue,
        p10_auto_cuant_utilizacion=data.p10_auto_cuant_utilizacion,
        p11_bloqueantes_staffing=data.p11_bloqueantes_staffing,
        p12_bloqueantes_supply=data.p12_bloqueantes_supply,
        p13_bloqueantes_energy=data.p13_bloqueantes_energy,
        p14_bloqueantes_regulacion=data.p14_bloqueantes_regulacion,
        p15_bloqueantes_expertise=data.p15_bloqueantes_expertise,
        # Scores calculados (cacheados para no recalcular)
        score_visibilidad=scores["visibilidad"],
        score_friccion=scores["friccion"],
        score_latencia=scores["latencia"],
        score_auto_cuantificacion=scores["auto_cuantificacion"],
        score_bloqueantes=scores["bloqueantes"],
        # Percentiles calculados (cacheados)
        percentile_visibilidad=percentiles["visibilidad"],
        percentile_friccion=percentiles["friccion"],
        percentile_latencia=percentiles["latencia"],
        percentile_auto_cuantificacion=percentiles["auto_cuantificacion"],
        percentile_bloqueantes=percentiles["bloqueantes"],
        percentile_general=percentiles["general"],
    )

    session.add(evaluation)
    await session.commit()
    await session.refresh(evaluation)

    return evaluation


# ─────────────────────────────────────────────────────────────
# 7. Construir Respuesta JSON para el Frontend
# ─────────────────────────────────────────────────────────────

def build_result_response(evaluation: UserEvaluation) -> BenchmarkResponse:
    """
    Transforma un UserEvaluation persistido en el schema oficial BenchmarkResponse (US-2).
    """
    scores = {
        "visibilidad": float(evaluation.score_visibilidad or 0.0),
        "friccion": float(evaluation.score_friccion or 0.0),
        "latencia": float(evaluation.score_latencia or 0.0),
        "auto_cuantificacion": float(evaluation.score_auto_cuantificacion or 0.0),
        "bloqueantes": float(evaluation.score_bloqueantes or 0.0),
    }

    percentiles = {
        "visibilidad": int(evaluation.percentile_visibilidad or 50),
        "friccion": int(evaluation.percentile_friccion or 50),
        "latencia": int(evaluation.percentile_latencia or 50),
        "auto_cuantificacion": int(evaluation.percentile_auto_cuantificacion or 50),
        "bloqueantes": int(evaluation.percentile_bloqueantes or 50),
        "general": int(evaluation.percentile_general or 50),
    }

    main_weakness_dim = get_main_weakness(percentiles)

    return BenchmarkResponse(
        evaluation_id=evaluation.evaluation_id,
        user_context=UserContextResponse(
            facility_size=evaluation.facility_size,
            region=evaluation.region,
        ),
        scores_likert=ScoresLikertResponse(
            visibilidad=scores["visibilidad"],
            friccion=scores["friccion"],
            latencia=scores["latencia"],
            auto_cuantificacion=scores["auto_cuantificacion"],
            bloqueantes=scores["bloqueantes"],
        ),
        percentiles=PercentilesResponse(
            visibilidad=percentiles["visibilidad"],
            friccion=percentiles["friccion"],
            latencia=percentiles["latencia"],
            auto_cuantificacion=percentiles["auto_cuantificacion"],
            bloqueantes=percentiles["bloqueantes"],
            general=percentiles["general"],
        ),
        main_weakness=main_weakness_dim,
        rebalancing_status=RebalancingStatusResponse(
            weight_public=1.0,
            weight_private=0.0,
        ),
    )




# ─────────────────────────────────────────────────────────────
# US-7 / Sección 8: Ponderación de Rebalanceo Bayesiano
# ─────────────────────────────────────────────────────────────

def calculate_rebalancing_weights(total_users: int) -> tuple[float, float]:
    """
    Pondera los benchmarks públicos vs privados según cuántos usuarios
    acumula la base de datos (Rebalanceo Bayesiano).

    Cuantos más usuarios privados, mayor peso se otorga a esos datos:
        - <= 10 usuarios:  100% público (1.0),   0% privado (0.0)
        - <= 50 usuarios:   80% público (0.8),  20% privado (0.2)
        - <= 200 usuarios:  60% público (0.6),  40% privado (0.4)
        - <= 500 usuarios:  40% público (0.4),  60% privado (0.6)
        - > 500 usuarios:   20% público (0.2),  80% privado (0.8)

    Args:
        total_users: Cantidad total de usuarios/evaluaciones en BD.

    Returns:
        Tupla (weight_public, weight_private) que suman 1.0.

    Raises:
        ValueError: Si total_users es un número negativo.

    Ejemplo:
        >>> calculate_rebalancing_weights(150)
        (0.6, 0.4)
    """
    if total_users < 0:
        raise ValueError("total_users no puede ser un número negativo.")

    if total_users <= 10:
        return (1.0, 0.0)
    elif total_users <= 50:
        return (0.8, 0.2)
    elif total_users <= 200:
        return (0.6, 0.4)
    elif total_users <= 500:
        return (0.4, 0.6)
    else:
        return (0.2, 0.8)


# ─────────────────────────────────────────────────────────────
# US-8 / Sección 9: Orquestación del Flujo Completo
# ─────────────────────────────────────────────────────────────

async def generate_benchmark_response(
    evaluation_id: UUID,
    db: AsyncSession,
) -> BenchmarkResponse:
    """
    US-8: Coordina todo el flujo de cálculo del benchmark a partir del ID de evaluación
    y genera el BenchmarkResponse tipado listo para el consumo del frontend.

    Flujo:
        1. Trae la evaluación de la base de datos (404 si no existe).
        2. Agrupa y calcula los 5 sub-scores Likert (US-4).
        3. Calcula los percentiles dimensionales y el percentil general (US-5).
        4. Identifica la debilidad principal respetando la jerarquía de desempate (US-6).
        5. Cuenta los usuarios en BD y calcula los pesos de rebalanceo (US-7).
        6. Construye y retorna la instancia de BenchmarkResponse (US-2).

    Args:
        evaluation_id: Identificador UUID de la evaluación a procesar.
        db: Sesión asíncrona de base de datos SQLAlchemy.

    Returns:
        Instancia de BenchmarkResponse serializable a JSON.

    Raises:
        HTTPException: 404 si la evaluación no existe.
    """
    # 1. Traer la evaluación del usuario
    result = await db.execute(
        select(UserEvaluation).where(UserEvaluation.evaluation_id == evaluation_id)
    )
    evaluation = result.scalar_one_or_none()

    if not evaluation:
        raise EvaluationNotFoundException(evaluation_id)


    # 2. Calcular los 5 sub-scores por dimensión (US-4)
    scores: dict[str, float] = {}
    for dimension, questions in DIMENSION_QUESTIONS.items():
        cached_score = getattr(evaluation, f"score_{dimension}", None)
        if cached_score is not None:
            scores[dimension] = float(cached_score)
        else:
            values = [getattr(evaluation, q) for q in questions]
            scores[dimension] = round(calculate_dimension_score(values), 2)

    # 3. Calcular los 5 percentiles dimensionales (US-5)
    percentiles: dict[str, int] = {}
    for dimension in DIMENSION_QUESTIONS:
        cached_pct = getattr(evaluation, f"percentile_{dimension}", None)
        if cached_pct is not None:
            percentiles[dimension] = int(cached_pct)
        else:
            user_score = scores[dimension]
            pct = await calculate_dimension_percentile(dimension, user_score, db)
            percentiles[dimension] = pct

    # Percentil general
    cached_general = getattr(evaluation, "percentile_general", None)
    if cached_general is not None:
        percentiles["general"] = int(cached_general)
    else:
        avg_pct = sum(percentiles[dim] for dim in DIMENSION_QUESTIONS) / len(DIMENSION_QUESTIONS)
        percentiles["general"] = round(avg_pct)

    # 4. Identificar la debilidad principal (US-6)
    main_weakness_dim = get_main_weakness(percentiles)

    # 5. Contar el total de usuarios en BD y calcular rebalanceo bayesiano (US-7)
    total_users_result = await db.execute(
        select(func.count(UserEvaluation.evaluation_id))
    )
    total_users = total_users_result.scalar() or 0
    weight_pub, weight_priv = calculate_rebalancing_weights(total_users)

    # 6. Construir BenchmarkResponse fuertemente tipado (US-2)
    return BenchmarkResponse(
        evaluation_id=evaluation.evaluation_id,
        user_context=UserContextResponse(
            facility_size=evaluation.facility_size,
            region=evaluation.region,
        ),
        scores_likert=ScoresLikertResponse(
            visibilidad=scores["visibilidad"],
            friccion=scores["friccion"],
            latencia=scores["latencia"],
            auto_cuantificacion=scores["auto_cuantificacion"],
            bloqueantes=scores["bloqueantes"],
        ),
        percentiles=PercentilesResponse(
            visibilidad=percentiles["visibilidad"],
            friccion=percentiles["friccion"],
            latencia=percentiles["latencia"],
            auto_cuantificacion=percentiles["auto_cuantificacion"],
            bloqueantes=percentiles["bloqueantes"],
            general=percentiles["general"],
        ),
        main_weakness=main_weakness_dim,
        rebalancing_status=RebalancingStatusResponse(
            weight_public=weight_pub,
            weight_private=weight_priv,
        ),
    )


