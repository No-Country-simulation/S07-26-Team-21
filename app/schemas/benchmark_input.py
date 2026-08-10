from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class FacilitySizeEnum(str, Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    MEGA = "mega"


class RegionEnum(str, Enum):
    LATAM = "latam"
    USA = "usa"
    EUROPE = "europe"
    APAC = "apac"


class BenchmarkRequest(BaseModel):
    """
    Schema de Entrada: Valida el payload enviado por el Frontend.
    Contiene 2 metadatos obligatorios (facility_size, region) y 15 scores Likert (p1 a p15).
    """

    # Metadatos de Contexto
    facility_size: FacilitySizeEnum = Field(
        ...,
        description="Tamaño de la instalación (small, medium, large, mega)",
        examples=[FacilitySizeEnum.MEDIUM],
    )
    region: RegionEnum = Field(
        ...,
        description="Región geográfica (latam, usa, europe, apac)",
        examples=[RegionEnum.LATAM],
    )
    facility_type: Optional[str] = Field(
        default="Enterprise",
        description="Tipo de centro de datos (opcional)",
        examples=["Enterprise"],
    )

    # 15 Preguntas Likert (Validación estricta de 1 a 5, no nulos)
    p1: int = Field(..., ge=1, le=5, description="Visibilidad de herramientas")
    p2: int = Field(..., ge=1, le=5, description="Visibilidad de dashboards")
    p3: int = Field(..., ge=1, le=5, description="Visibilidad de telemetría")

    p4: int = Field(..., ge=1, le=5, description="Fricción en energía")
    p5: int = Field(..., ge=1, le=5, description="Fricción en cooling")

    p6: int = Field(..., ge=1, le=5, description="Latencia en procesos manuales")
    p7: int = Field(..., ge=1, le=5, description="Latencia en procesos semi-automatizados")
    p8: int = Field(..., ge=1, le=5, description="Latencia en procesos full-automatizados")

    p9: int = Field(..., ge=1, le=5, description="Auto-cuantificación de PUE")
    p10: int = Field(..., ge=1, le=5, description="Auto-cuantificación de utilización")

    p11: int = Field(..., ge=1, le=5, description="Bloqueantes: staffing / personal")
    p12: int = Field(..., ge=1, le=5, description="Bloqueantes: supply chain")
    p13: int = Field(..., ge=1, le=5, description="Bloqueantes: energía / disponibilidad")
    p14: int = Field(..., ge=1, le=5, description="Bloqueantes: regulación y cumplimiento")
    p15: int = Field(..., ge=1, le=5, description="Bloqueantes: expertise técnico")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
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
        }
    )


# Alias para retrocompatibilidad
BenchmarkSubmitSchema = BenchmarkRequest