from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.benchmark_input import FacilitySizeEnum, RegionEnum


class UserContextResponse(BaseModel):
    """
    Metadatos de contexto del usuario evaluado.
    """

    facility_size: FacilitySizeEnum = Field(
        ..., description="Tamaño del centro de datos (small, medium, large, mega)"
    )
    region: RegionEnum = Field(
        ..., description="Región geográfica (latam, usa, europe, apac)"
    )


class ScoresLikertResponse(BaseModel):
    """
    Scores promedio Likert (float) agrupados por dimensión de madurez.
    """

    visibilidad: float = Field(
        ..., description="Promedio Likert en visibilidad y observabilidad"
    )
    friccion: float = Field(
        ..., description="Promedio Likert en fricción operativa"
    )
    latencia: float = Field(
        ..., description="Promedio Likert en latencia de toma de decisiones"
    )
    auto_cuantificacion: float = Field(
        ..., description="Promedio Likert en auto-cuantificación de métricas"
    )
    bloqueantes: float = Field(
        ..., description="Promedio Likert en bloqueantes operativos"
    )


class PercentilesResponse(BaseModel):
    """
    Percentiles calculados (int) por dimensión y percentil general frente a la industria.
    """

    visibilidad: int = Field(..., description="Percentil en visibilidad")
    friccion: int = Field(..., description="Percentil en fricción")
    latencia: int = Field(..., description="Percentil en latencia")
    auto_cuantificacion: int = Field(
        ..., description="Percentil en auto-cuantificación"
    )
    bloqueantes: int = Field(..., description="Percentil en bloqueantes")
    general: int = Field(..., description="Percentil general ponderado")


class RebalancingStatusResponse(BaseModel):
    """
    Pesos del rebalanceo bayesiano entre datos públicos e internos.
    """

    weight_public: float = Field(
        ..., description="Peso asignado a datos públicos de referencia"
    )
    weight_private: float = Field(
        ..., description="Peso asignado a datos propios recolectados"
    )


class PeerComparison(BaseModel):
    """
    US-17: Comparación relativa frente a peers del mismo tamaño y región.
    Aplica K-anonimato para proteger la privacidad estadística.
    """

    peers_count: int = Field(
        ..., description="Cantidad de evaluaciones de pares encontradas"
    )
    peer_average_score: float | None = Field(
        default=None, description="Score promedio de los pares en la dimensión"
    )
    your_score: float = Field(
        ..., description="Score del usuario en la dimensión evaluada"
    )
    gap_vs_peers: float | None = Field(
        default=None, description="Diferencia: your_score - peer_average_score"
    )
    percentile_vs_peers: int | None = Field(
        default=None, description="Percentil relativo entre pares (0-100)"
    )
    disclaimer: str | None = Field(
        default=None, description="Aviso de muestra limitada o K-anonimato"
    )
    message: str | None = Field(
        default=None, description="Mensaje explicativo o de estado"
    )


class MainWeaknessEnriched(BaseModel):
    """
    US-16: Diagnóstico enriquecido de la debilidad principal.
    """

    dimension: str = Field(
        ..., description="Nombre de la dimensión operativa con mayor oportunidad de mejora"
    )
    user_score: float = Field(
        ..., description="Score Likert promedio obtenido por el usuario"
    )
    top_quartile_average: float = Field(
        ..., description="Promedio de élite / cuartil superior en la dimensión"
    )
    gap: float = Field(
        ..., description="Brecha de mejora no negativa respecto a la élite (>= 0.0)"
    )
    recommendations: list[str] = Field(
        ..., description="Acciones técnicas prioritarias para mitigar la debilidad"
    )
    llm_generated: bool = Field(
        default=False, description="Flag indicador de generación vía IA o fallback"
    )

    def __str__(self) -> str:
        return self.dimension

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.dimension == other
        return super().__eq__(other)


class BenchmarkResponse(BaseModel):
    """
    Schema de Salida: Estructura uniforme retornada por el endpoint POST /submit y GET /results/{id}.
    Contiene exactamente las secciones requeridas por el Frontend.
    """

    evaluation_id: UUID = Field(
        ..., description="Identificador único UUID de la evaluación"
    )
    user_context: UserContextResponse = Field(
        ..., description="Contexto de la instalación evaluada"
    )
    scores_likert: ScoresLikertResponse = Field(
        ..., description="Promedios Likert por cada dimensión"
    )
    percentiles: PercentilesResponse = Field(
        ..., description="Percentiles alcanzados por dimensión y general"
    )
    main_weakness: MainWeaknessEnriched | str = Field(
        ...,
        description="Diagnóstico enriquecido de la debilidad principal (o nombre de dimensión)",
    )
    rebalancing_status: RebalancingStatusResponse = Field(
        ..., description="Estado de ponderación del rebalanceo"
    )
    peer_comparison: PeerComparison | None = Field(
        default=None,
        description="Comparación relativa contra peers del mismo tamaño y región",
    )



    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "evaluation_id": "123e4567-e89b-12d3-a456-426614174000",
                "user_context": {
                    "facility_size": "medium",
                    "region": "latam",
                },
                "scores_likert": {
                    "visibilidad": 3.67,
                    "friccion": 2.50,
                    "latencia": 4.00,
                    "auto_cuantificacion": 3.00,
                    "bloqueantes": 2.20,
                },
                "percentiles": {
                    "visibilidad": 65,
                    "friccion": 42,
                    "latencia": 80,
                    "auto_cuantificacion": 55,
                    "bloqueantes": 38,
                    "general": 60,
                },
                "main_weakness": "friccion",
                "rebalancing_status": {
                    "weight_public": 0.85,
                    "weight_private": 0.15,
                },
            }
        }
    )


# Alias para retrocompatibilidad
BenchmarkResultSchema = BenchmarkResponse