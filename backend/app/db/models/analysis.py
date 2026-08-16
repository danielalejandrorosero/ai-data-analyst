import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Text, Uuid, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AnalysisStatus(enum.StrEnum):
    """Estados de una ejecucion (SRS seccion 7.2)."""

    QUEUED = "QUEUED"
    PLANNING = "PLANNING"
    TOOL_RUNNING = "TOOL_RUNNING"
    ANALYZING = "ANALYZING"
    GENERATING_RESPONSE = "GENERATING_RESPONSE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"


TERMINAL_ANALYSIS_STATUSES = frozenset(
    {
        AnalysisStatus.COMPLETED,
        AnalysisStatus.FAILED,
        AnalysisStatus.CANCELLED,
        AnalysisStatus.TIMED_OUT,
    }
)


class Analysis(Base):
    """Solicitud y estado de un analisis (RF-020 a RF-025).

    `result_json` guarda un ARRAY con la evidencia de CADA consulta SQL
    exitosa de la corrida (sql/columns/rows/truncated cada una) - RF-022
    permite al agente ejecutar mas de una consulta para una pregunta
    compleja, asi que la evidencia final puede venir de varias. No es el
    historial completo de cada tool call (incluye los fallidos/rechazados),
    eso vive en tool_calls via agent_runs.

    `arq_job_id` referencia el job en la cola de workers/ (RF-025,
    Fase 4) - lo usa POST /analyses/{id}/cancel para pedirle a ARQ que
    aborte el job en curso. Nulo mientras el analysis corre sincronico
    (tests que llaman run_analysis directamente sin pasar por la API).
    """

    __tablename__ = "analyses"
    __table_args__ = (Index("ix_analyses_org_created_at", "organization_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[AnalysisStatus] = mapped_column(
        SAEnum(AnalysisStatus, name="analysis_status"),
        nullable=False,
        default=AnalysisStatus.QUEUED,
    )
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    arq_job_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
