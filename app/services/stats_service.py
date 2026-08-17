import asyncio
import time
from typing import Awaitable, Callable
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_evaluation import UserEvaluation
from app.schemas.benchmark_input import FacilitySizeEnum, RegionEnum
from app.schemas.benchmark_stats import BenchmarkStats


class StatsCache:
    """
    Caché en memoria asíncrono con TTL configurable y soporte para invalidación manual.
    """

    def __init__(self, ttl_seconds: int = 3600):
        self.ttl_seconds = ttl_seconds
        self._cached_data: BenchmarkStats | None = None
        self._cached_at: float = 0.0
        self._lock = asyncio.Lock()

    def is_valid(self) -> bool:
        return (
            self._cached_data is not None
            and (time.monotonic() - self._cached_at) < self.ttl_seconds
        )

    def get(self) -> BenchmarkStats | None:
        if self.is_valid():
            return self._cached_data
        return None

    def set(self, data: BenchmarkStats) -> None:
        self._cached_data = data
        self._cached_at = time.monotonic()

    def clear(self) -> None:
        """
        Invalida la caché de estadísticas forzando recálculo en la próxima consulta.
        """
        self._cached_data = None
        self._cached_at = 0.0


# Instancia global de caché de estadísticas (1 hora de TTL)
stats_cache = StatsCache(ttl_seconds=3600)


async def get_platform_stats(
    db: AsyncSession, bypass_cache: bool = False
) -> BenchmarkStats:
    """
    US-18: Retorna las métricas agregadas globales de la plataforma.
    Aplica caché en memoria de 1 hora y sanitización defensiva contra NULLs.
    """
    # 1. Retornar desde caché si es válida y no se solicitó bypass
    if not bypass_cache and stats_cache.is_valid():
        cached = stats_cache.get()
        if cached is not None:
            return cached

    # 2. Inicializar diccionarios base con todas las opciones en 0 / 0.0
    by_region = {r.value: 0 for r in RegionEnum}
    by_size = {s.value: 0 for s in FacilitySizeEnum}
    evaluations_by_dimension_strength = {
        "visibilidad": 0.0,
        "friccion": 0.0,
        "latencia": 0.0,
        "auto_cuantificacion": 0.0,
        "bloqueantes": 0.0,
    }

    # 3. Conteo total de evaluaciones
    total_evals_query = select(func.count(UserEvaluation.evaluation_id))
    total_evals_res = await db.execute(total_evals_query)
    total_evaluations = total_evals_res.scalar() or 0

    if total_evaluations > 0:
        # 4. Distribución por región
        region_query = select(
            UserEvaluation.region, func.count(UserEvaluation.evaluation_id)
        ).group_by(UserEvaluation.region)
        region_res = await db.execute(region_query)
        for r_name, r_count in region_res.all():
            if r_name in by_region:
                by_region[r_name] = int(r_count)

        # 5. Distribución por tamaño de facility
        size_query = select(
            UserEvaluation.facility_size, func.count(UserEvaluation.evaluation_id)
        ).group_by(UserEvaluation.facility_size)
        size_res = await db.execute(size_query)
        for s_name, s_count in size_res.all():
            if s_name in by_size:
                by_size[s_name] = int(s_count)

        # 6. Promedio global de percentil general y promedios por dimensión
        averages_query = select(
            func.coalesce(func.avg(UserEvaluation.percentile_general), 0.0),
            func.coalesce(func.avg(UserEvaluation.score_visibilidad), 0.0),
            func.coalesce(func.avg(UserEvaluation.score_friccion), 0.0),
            func.coalesce(func.avg(UserEvaluation.score_latencia), 0.0),
            func.coalesce(func.avg(UserEvaluation.score_auto_cuantificacion), 0.0),
            func.coalesce(func.avg(UserEvaluation.score_bloqueantes), 0.0),
        )
        averages_res = await db.execute(averages_query)
        avg_row = averages_res.first()

        avg_gen_pct = round(float(avg_row[0] or 0.0), 2)
        evaluations_by_dimension_strength = {
            "visibilidad": round(float(avg_row[1] or 0.0), 2),
            "friccion": round(float(avg_row[2] or 0.0), 2),
            "latencia": round(float(avg_row[3] or 0.0), 2),
            "auto_cuantificacion": round(float(avg_row[4] or 0.0), 2),
            "bloqueantes": round(float(avg_row[5] or 0.0), 2),
        }
    else:
        avg_gen_pct = 0.0

    stats = BenchmarkStats(
        total_evaluations=total_evaluations,
        by_region=by_region,
        by_size=by_size,
        average_general_percentile=avg_gen_pct,
        evaluations_by_dimension_strength=evaluations_by_dimension_strength,
    )

    # Guardar en caché
    stats_cache.set(stats)
    return stats
