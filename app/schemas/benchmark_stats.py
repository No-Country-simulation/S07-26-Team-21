from typing import Dict
from pydantic import BaseModel, Field, ConfigDict


class BenchmarkStats(BaseModel):
    """
    US-18: Métricas agregadas de la plataforma para landing page y credibilidad.
    """

    total_evaluations: int = Field(
        ..., description="Total acumulado de evaluaciones procesadas"
    )
    by_region: Dict[str, int] = Field(
        ..., description="Cantidad de evaluaciones agrupadas por región geográfica"
    )
    by_size: Dict[str, int] = Field(
        ..., description="Cantidad de evaluaciones agrupadas por tamaño de instalación"
    )
    average_general_percentile: float = Field(
        ..., description="Promedio global de percentiles generales obtenidos"
    )
    evaluations_by_dimension_strength: Dict[str, float] = Field(
        ..., description="Promedio de scores Likert por dimensión operativa"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_evaluations": 165,
                "by_region": {
                    "latam": 45,
                    "usa": 70,
                    "europe": 35,
                    "apac": 15,
                },
                "by_size": {
                    "small": 30,
                    "medium": 75,
                    "large": 45,
                    "mega": 15,
                },
                "average_general_percentile": 58.4,
                "evaluations_by_dimension_strength": {
                    "visibilidad": 3.65,
                    "friccion": 2.80,
                    "latencia": 3.10,
                    "auto_cuantificacion": 3.45,
                    "bloqueantes": 2.90,
                },
            }
        }
    )
