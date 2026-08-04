from datetime import date
from typing import Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel


class MainWeaknessSchema(BaseModel):
    dimension: str
    percentile: int
    user_score: float


class BenchmarkResultSchema(BaseModel):
    """
    Schema de Salida: Estructura la respuesta para el Dashboard de Resultados en React.
    """

    evaluation_id: UUID
    created_at: date
    user_context: Dict[str, str]
    scores_likert: Dict[str, float]
    percentiles: Dict[str, int]
    main_weakness: Optional[MainWeaknessSchema] = None
    recommendations: List[str] = []


class BenchmarkResponseCreatedSchema(BaseModel):
    """
    Respuesta liviana e inmediata al hacer POST /submit.
    """

    evaluation_id: UUID
    message: str = "Evaluación procesada exitosamente"