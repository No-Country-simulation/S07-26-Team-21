import uuid
from datetime import datetime, date
from sqlalchemy import String, Integer, Float, Date, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class UserEvaluation(Base):
    __tablename__ = "user_evaluations"

    # UUID v4: Garantiza aleatoriedad total (No estático/incremental)
    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # CONTEXTO
    facility_size: Mapped[str] = mapped_column(String(20), nullable=False)
    facility_type: Mapped[str] = mapped_column(
        String(30), default="Enterprise"
    )
    region: Mapped[str] = mapped_column(String(20), nullable=False)

    # ANONIMIZACIÓN DE FECHA: Guardamos solo la fecha (YYYY-MM-DD), NO la hora/minuto/segundo exacto.
    # Esto evita la correlación por marcas de tiempo en logs HTTP.
    created_at: Mapped[date] = mapped_column(
        Date, default=date.today, nullable=False
    )

    # 15 Preguntas Likert (1 a 5)
    p1_visibilidad_herramientas: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    p2_visibilidad_dashboards: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    p3_visibilidad_telemetry: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    p4_friccion_energia: Mapped[int] = mapped_column(Integer, nullable=False)
    p5_friccion_cooling: Mapped[int] = mapped_column(Integer, nullable=False)

    p6_latencia_manual: Mapped[int] = mapped_column(Integer, nullable=False)
    p7_latencia_semi_auto: Mapped[int] = mapped_column(Integer, nullable=False)
    p8_latencia_full_auto: Mapped[int] = mapped_column(Integer, nullable=False)

    p9_auto_cuant_pue: Mapped[int] = mapped_column(Integer, nullable=False)
    p10_auto_cuant_utilizacion: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    p11_bloqueantes_staffing: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    p12_bloqueantes_supply: Mapped[int] = mapped_column(Integer, nullable=False)
    p13_bloqueantes_energy: Mapped[int] = mapped_column(Integer, nullable=False)
    p14_bloqueantes_regulacion: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    p15_bloqueantes_expertise: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    # Sub-scores Likert Promediados (Cacheados)
    score_visibilidad: Mapped[float] = mapped_column(Float, nullable=True)
    score_friccion: Mapped[float] = mapped_column(Float, nullable=True)
    score_latencia: Mapped[float] = mapped_column(Float, nullable=True)
    score_auto_cuantificacion: Mapped[float] = mapped_column(
        Float, nullable=True
    )
    score_bloqueantes: Mapped[float] = mapped_column(Float, nullable=True)

    # Percentiles Calculados (Cacheados)
    percentile_visibilidad: Mapped[int] = mapped_column(Integer, nullable=True)
    percentile_friccion: Mapped[int] = mapped_column(Integer, nullable=True)
    percentile_latencia: Mapped[int] = mapped_column(Integer, nullable=True)
    percentile_auto_cuantificacion: Mapped[int] = mapped_column(
        Integer, nullable=True
    )
    percentile_bloqueantes: Mapped[int] = mapped_column(Integer, nullable=True)
    percentile_general: Mapped[int] = mapped_column(Integer, nullable=True)