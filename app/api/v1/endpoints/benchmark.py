import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user_evaluation import UserEvaluation
from app.schemas.benchmark_input import BenchmarkRequest
from app.schemas.benchmark_output import BenchmarkResponse
from app.schemas.benchmark_stats import BenchmarkStats
from app.services.scoring_engine import generate_benchmark_response
from app.services.stats_service import get_platform_stats, stats_cache

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/submit",
    response_model=BenchmarkResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Enviar evaluación de 15 preguntas Likert y obtener benchmark",
    description=(
        "Recibe las 15 respuestas Likert y el contexto de infraestructura, "
        "persiste la evaluación en la base de datos, calcula los sub-scores, "
        "percentiles ponderados, debilidad principal y retorna el BenchmarkResponse."
    ),
)
async def submit_benchmark(
    payload: BenchmarkRequest,
    db: AsyncSession = Depends(get_db),
) -> BenchmarkResponse:
    """
    US-9: Procesa el envío de una nueva evaluación de benchmark.
    """
    try:
        # 1. Crear la entidad UserEvaluation a partir del payload validado
        evaluation = UserEvaluation(
            facility_size=payload.facility_size.value,
            region=payload.region.value,
            facility_type=payload.facility_type or "Enterprise",
            p1_visibilidad_herramientas=payload.p1,
            p2_visibilidad_dashboards=payload.p2,
            p3_visibilidad_telemetry=payload.p3,
            p4_friccion_energia=payload.p4,
            p5_friccion_cooling=payload.p5,
            p6_latencia_manual=payload.p6,
            p7_latencia_semi_auto=payload.p7,
            p8_latencia_full_auto=payload.p8,
            p9_auto_cuant_pue=payload.p9,
            p10_auto_cuant_utilizacion=payload.p10,
            p11_bloqueantes_staffing=payload.p11,
            p12_bloqueantes_supply=payload.p12,
            p13_bloqueantes_energy=payload.p13,
            p14_bloqueantes_regulacion=payload.p14,
            p15_bloqueantes_expertise=payload.p15,
        )

        # 2. Persistir en la base de datos
        db.add(evaluation)
        await db.commit()
        await db.refresh(evaluation)

        # Invalida la caché de estadísticas para reflejar la nueva evaluación en tiempo real
        stats_cache.clear()

        # 3. Orquestar el cálculo completo y generar la respuesta (US-8)
        response = await generate_benchmark_response(evaluation.evaluation_id, db)
        return response

    except HTTPException:
        # Re-lanzar HTTPExceptions sin alterar el status code
        raise
    except Exception as exc:
        logger.error(f"Error inesperado al procesar el benchmark: {exc}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor al procesar la evaluación de benchmark.",
        )


@router.get(
    "/stats",
    response_model=BenchmarkStats,
    status_code=status.HTTP_200_OK,
    summary="Obtener métricas agregadas globales de la plataforma",
    description=(
        "US-18: Retorna métricas globales agregadas (total de evaluaciones, distribuciones, "
        "percentil promedio y promedios por dimensión) con caché en memoria de 1 hora."
    ),
)
async def get_benchmark_stats(
    db: AsyncSession = Depends(get_db),
) -> BenchmarkStats:
    """
    US-18: Retorna estadísticas globales de la plataforma para landing page y dashboards.
    """
    return await get_platform_stats(db)

