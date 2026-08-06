from sqlalchemy import String, Integer, Float, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from datetime import datetime


class IndustryBenchmark(Base):
    """
    Modelo ORM para la tabla 'industry_benchmarks'.
    Almacena las constantes de referencia de las 7 fuentes académicas e industriales.
    """
    __tablename__ = "industry_benchmarks"

    benchmark_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    dimension: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_name: Mapped[str] = mapped_column(String(100), nullable=False)
    source_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    source_region: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_reliability: Mapped[float] = mapped_column(Float, nullable=False)

    # Nivel 1: Malo / Legacy (Likert 1)
    level_1_description: Mapped[str] = mapped_column(Text, nullable=False)
    level_1_metric_value: Mapped[float] = mapped_column(Float, nullable=True)
    level_1_metric_unit: Mapped[str] = mapped_column(String(20), nullable=True)
    level_1_likert_equivalent: Mapped[int] = mapped_column(Integer, default=1)

    # Nivel 3: Promedio Industria (Likert 3)
    level_3_description: Mapped[str] = mapped_column(Text, nullable=False)
    level_3_metric_value: Mapped[float] = mapped_column(Float, nullable=True)
    level_3_metric_unit: Mapped[str] = mapped_column(String(20), nullable=True)
    level_3_likert_equivalent: Mapped[int] = mapped_column(Integer, default=3)

    # Nivel 5: Élite / Best-in-Class (Likert 5)
    level_5_description: Mapped[str] = mapped_column(Text, nullable=False)
    level_5_metric_value: Mapped[float] = mapped_column(Float, nullable=True)
    level_5_metric_unit: Mapped[str] = mapped_column(String(20), nullable=True)
    level_5_likert_equivalent: Mapped[int] = mapped_column(Integer, default=5)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())