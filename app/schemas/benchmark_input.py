from pydantic import BaseModel, Field


class BenchmarkSubmitSchema(BaseModel):
    """
    Schema de Entrada: Valida el payload enviando por el Frontend.
    Contiene las 15 preguntas Likert (1 a 5) y las 3 variables de contexto.
    """

    # Contexto
    facility_size: str = Field(
        ...,
        examples=["mediano"],
        description="Tamaño de la instalación (small, medium, large, mega)",
    )
    facility_type: str = Field(
        default="Enterprise",
        examples=["Enterprise"],
        description="Tipo de centro de datos",
    )
    region: str = Field(
        ..., examples=["latam"], description="Región geográfica"
    )

    # 15 Preguntas Likert (Validación estricta de 1 a 5)
    p1_visibilidad_herramientas: int = Field(..., ge=1, le=5)
    p2_visibilidad_dashboards: int = Field(..., ge=1, le=5)
    p3_visibilidad_telemetry: int = Field(..., ge=1, le=5)

    p4_friccion_energia: int = Field(..., ge=1, le=5)
    p5_friccion_cooling: int = Field(..., ge=1, le=5)

    p6_latencia_manual: int = Field(..., ge=1, le=5)
    p7_latencia_semi_auto: int = Field(..., ge=1, le=5)
    p8_latencia_full_auto: int = Field(..., ge=1, le=5)

    p9_auto_cuant_pue: int = Field(..., ge=1, le=5)
    p10_auto_cuant_utilizacion: int = Field(..., ge=1, le=5)

    p11_bloqueantes_staffing: int = Field(..., ge=1, le=5)
    p12_bloqueantes_supply: int = Field(..., ge=1, le=5)
    p13_bloqueantes_energy: int = Field(..., ge=1, le=5)
    p14_bloqueantes_regulacion: int = Field(..., ge=1, le=5)
    p15_bloqueantes_expertise: int = Field(..., ge=1, le=5)