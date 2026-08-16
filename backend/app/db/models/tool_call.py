import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ToolCallStatus(enum.StrEnum):
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"


class ToolCall(Base):
    """Cada invocacion de una tool del agente (RF-023, RF-033).

    `input_json` guarda el input real de la tool (ej. la sentencia SQL
    generada) para que la respuesta final pueda mostrar de donde salio
    cada hallazgo (RF-024, RF-042 - "ver la consulta origen"). `input_hash`
    es una referencia estable para auditoria/deduplicacion (SRS seccion 6
    lista este campo explicitamente). `output_summary` NO guarda las filas
    completas del resultado (principio de persistencia SRS 6.1) - eso vive
    transitoriamente en Analysis.result_json para la ultima consulta exitosa.
    """

    __tablename__ = "tool_calls"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    agent_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tool: Mapped[str] = mapped_column(String(100), nullable=False)
    input_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    output_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[ToolCallStatus] = mapped_column(
        SAEnum(ToolCallStatus, name="tool_call_status"), nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
