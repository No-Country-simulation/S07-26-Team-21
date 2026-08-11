"""
Motor de Scoring – BENCHMARK·DC Engine
=======================================
Calcula scores por dimensión, percentiles relativos a la industria,
identifica la debilidad principal y genera recomendaciones.

Flujo:
    1. compute_dimension_scores()  → Promedio Likert por dimensión (1.0 – 5.0)
    2. normalize_score()           → Escala 0-100 para visualización
    3. compute_percentiles()       → Posición relativa vs. evaluaciones previas
    4. identify_main_weakness()    → Dimensión con menor percentil
    5. generate_recommendations()  → Recomendaciones priorizadas
    6. process_evaluation()        → Orquesta todo y persiste en BD
    7. build_result_response()     → Construye el JSON de respuesta para React
"""

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_evaluation import UserEvaluation
from app.schemas.benchmark_input import BenchmarkSubmitSchema
from app.schemas.benchmark_output import (
    BenchmarkResultSchema,
    MainWeaknessSchema,
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
        scores[dimension] = round(sum(values) / len(values), 2)

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
# 3. Calcular Percentiles vs. Evaluaciones Previas
# ─────────────────────────────────────────────────────────────

async def compute_percentiles(
    session: AsyncSession,
    scores: dict[str, float],
) -> dict[str, int]:
    """
    Calcula el percentil de cada dimensión comparando con todas las
    evaluaciones previas almacenadas en la base de datos.

    Fórmula:
        Percentil = (evaluaciones con score menor / total) × 100

    Si no hay evaluaciones previas (primera evaluación), se asigna
    percentil 50 como posición media de referencia.
    """
    percentiles: dict[str, int] = {}

    # Contar evaluaciones previas que ya tienen scores calculados
    total_result = await session.execute(
        select(func.count(UserEvaluation.evaluation_id)).where(
            UserEvaluation.score_visibilidad.isnot(None)
        )
    )
    total = total_result.scalar() or 0

    if total == 0:
        # Primera evaluación: percentil 50 por defecto en todas las dimensiones
        for dim in DIMENSION_QUESTIONS:
            percentiles[dim] = 50
        percentiles["general"] = 50
        return percentiles

    # Calcular percentil por dimensión
    for dim, score_col in SCORE_COLUMNS.items():
        user_score = scores[dim]

        # Contar cuántas evaluaciones tienen un score MENOR al del usuario
        lower_result = await session.execute(
            select(func.count(UserEvaluation.evaluation_id)).where(
                score_col < user_score,
                score_col.isnot(None),
            )
        )
        lower_count = lower_result.scalar() or 0

        percentiles[dim] = round((lower_count / total) * 100)

    # Percentil general: promedio de los percentiles dimensionales
    avg_percentile = sum(percentiles.values()) / len(percentiles)
    percentiles["general"] = round(avg_percentile)

    return percentiles


# ─────────────────────────────────────────────────────────────
# 4. Identificar la Debilidad Principal
# ─────────────────────────────────────────────────────────────

def identify_main_weakness(
    scores: dict[str, float],
    percentiles: dict[str, int],
) -> MainWeaknessSchema | None:
    """
    Retorna la dimensión con el percentil más bajo.
    Es el área donde el usuario tiene mayor oportunidad de mejora.
    """
    # Filtrar solo dimensiones reales (excluir "general")
    dim_percentiles = {
        k: v for k, v in percentiles.items() if k != "general"
    }

    if not dim_percentiles:
        return None

    weakest_dim = min(dim_percentiles, key=dim_percentiles.get)

    return MainWeaknessSchema(
        dimension=DIMENSION_LABELS.get(weakest_dim, weakest_dim),
        percentile=dim_percentiles[weakest_dim],
        user_score=scores[weakest_dim],
    )


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

def build_result_response(evaluation: UserEvaluation) -> BenchmarkResultSchema:
    """
    Transforma un UserEvaluation persistido en el schema de respuesta
    que consume el dashboard React.

    Incluye: scores, percentiles, debilidad principal y recomendaciones.
    """
    scores = {
        "visibilidad": evaluation.score_visibilidad,
        "friccion": evaluation.score_friccion,
        "latencia": evaluation.score_latencia,
        "auto_cuantificacion": evaluation.score_auto_cuantificacion,
        "bloqueantes": evaluation.score_bloqueantes,
    }

    percentiles = {
        "visibilidad": evaluation.percentile_visibilidad,
        "friccion": evaluation.percentile_friccion,
        "latencia": evaluation.percentile_latencia,
        "auto_cuantificacion": evaluation.percentile_auto_cuantificacion,
        "bloqueantes": evaluation.percentile_bloqueantes,
        "general": evaluation.percentile_general,
    }

    return BenchmarkResultSchema(
        evaluation_id=evaluation.evaluation_id,
        created_at=evaluation.created_at,
        user_context={
            "facility_size": evaluation.facility_size,
            "facility_type": evaluation.facility_type,
            "region": evaluation.region,
        },
        scores_likert=scores,
        percentiles=percentiles,
        main_weakness=identify_main_weakness(scores, percentiles),
        recommendations=generate_recommendations(scores, percentiles),
    )
