import uuid
from datetime import date
from sqlalchemy import CheckConstraint, String, Integer, Float, Date, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class UserEvaluation(Base):
    """
    Evaluación de madurez operativa de un Data Center (15 preguntas
    Likert 1-5, agrupadas en 5 dimensiones):

        Visibilidad:            p1, p2, p3
        Fricción:               p4, p5
        Latencia:               p6, p7, p8
        Auto-cuantificación:    p9, p10
        Bloqueantes:            p11-p15
    """

    __tablename__ = "user_evaluations"

    __table_args__ = (
        # Restricciones de valores válidos para contexto
        CheckConstraint(
            "facility_size IN ('small', 'medium', 'large', 'mega')",
            name="ck_user_evaluations_facility_size",
        ),
        CheckConstraint(
            "region IN ('latam', 'usa', 'europe', 'apac')",
            name="ck_user_evaluations_region",
        ),
        # CHECK (1-5) para las 15 preguntas Likert
        CheckConstraint(
            "p1_visibilidad_herramientas BETWEEN 1 AND 5", name="ck_p1_range"
        ),
        CheckConstraint(
            "p2_visibilidad_dashboards BETWEEN 1 AND 5", name="ck_p2_range"
        ),
        CheckConstraint(
            "p3_visibilidad_telemetry BETWEEN 1 AND 5", name="ck_p3_range"
        ),
        CheckConstraint(
            "p4_friccion_energia BETWEEN 1 AND 5", name="ck_p4_range"
        ),
        CheckConstraint(
            "p5_friccion_cooling BETWEEN 1 AND 5", name="ck_p5_range"
        ),
        CheckConstraint(
            "p6_latencia_manual BETWEEN 1 AND 5", name="ck_p6_range"
        ),
        CheckConstraint(
            "p7_latencia_semi_auto BETWEEN 1 AND 5", name="ck_p7_range"
        ),
        CheckConstraint(
            "p8_latencia_full_auto BETWEEN 1 AND 5", name="ck_p8_range"
        ),
        CheckConstraint(
            "p9_auto_cuant_pue BETWEEN 1 AND 5", name="ck_p9_range"
        ),
        CheckConstraint(
            "p10_auto_cuant_utilizacion BETWEEN 1 AND 5", name="ck_p10_range"
        ),
        CheckConstraint(
            "p11_bloqueantes_staffing BETWEEN 1 AND 5", name="ck_p11_range"
        ),
        CheckConstraint(
            "p12_bloqueantes_supply BETWEEN 1 AND 5", name="ck_p12_range"
        ),
        CheckConstraint(
            "p13_bloqueantes_energy BETWEEN 1 AND 5", name="ck_p13_range"
        ),
        CheckConstraint(
            "p14_bloqueantes_regulacion BETWEEN 1 AND 5", name="ck_p14_range"
        ),
        CheckConstraint(
            "p15_bloqueantes_expertise BETWEEN 1 AND 5", name="ck_p15_range"
        ),
        # Índice compuesto para optimizar consultas de peers por cohorte
        Index("ix_user_evaluations_size_region", "facility_size", "region"),
    )


    # UUID v4: Garantiza aleatoriedad total (No estático/incremental)
    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # CONTEXTO
    facility_size: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )
    facility_type: Mapped[str] = mapped_column(
        String(30), default="Enterprise"
    )
    region: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )

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
    p12_bloqueantes_supply: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    p13_bloqueantes_energy: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
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

    def __repr__(self) -> str:
        return (
            f"<UserEvaluation id={self.evaluation_id} "
            f"size={self.facility_size} region={self.region} "
            f"created_at={self.created_at}>"
        )
