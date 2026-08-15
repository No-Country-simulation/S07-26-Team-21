"""
app/exceptions.py

Jerarquía de excepciones personalizadas para el dominio BENCHMARK·DC Engine.
Todas las excepciones retornan detalles descriptivos para el frontend.
"""

from typing import Any
from uuid import UUID


class BenchmarkException(Exception):
    """Clase base para todas las excepciones del dominio de Benchmark."""

    def __init__(self, detail: str = "Ocurrió un error en el motor de benchmark."):
        self.detail = detail
        super().__init__(self.detail)


class EvaluationNotFoundException(BenchmarkException):
    """Excepción lanzada cuando una evaluación no existe en la base de datos (HTTP 404)."""

    def __init__(self, evaluation_id: str | UUID):
        self.evaluation_id = str(evaluation_id)
        self.detail = f"Evaluación con ID '{self.evaluation_id}' no encontrada."
        super().__init__(self.detail)


class InvalidPayloadException(BenchmarkException):
    """Excepción lanzada cuando el payload o datos de entrada no son válidos (HTTP 422)."""

    def __init__(self, detail: str = "El payload proporcionado no es válido."):
        self.detail = detail
        super().__init__(self.detail)


class DatabaseException(BenchmarkException):
    """Excepción lanzada cuando ocurre un error de persistencia o conexión en la BD (HTTP 500)."""

    def __init__(
        self,
        detail: str = "Error interno del servidor al procesar la solicitud.",
        original_error: Any = None,
    ):
        self.detail = detail
        self.original_error = original_error
        super().__init__(self.detail)
