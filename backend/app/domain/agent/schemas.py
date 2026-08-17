import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.db.models.analysis import AnalysisStatus


class AnalysisCreateRequest(BaseModel):
    dataset_id: uuid.UUID
    question: str = Field(min_length=1, max_length=2000)


class ToolCallOut(BaseModel):
    tool: str
    status: str
    duration_ms: int
    output_summary: dict[str, Any] | None
    error_message: str | None

    model_config = {"from_attributes": True}


class AnalysisListItemOut(BaseModel):
    """Version liviana para CU-08 (historial) - sin el trace de tool_calls,
    que solo hace falta en el detalle (GET /analyses/{id})."""

    id: uuid.UUID
    dataset_id: uuid.UUID
    question: str
    status: AnalysisStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class AnalysisCancelOut(BaseModel):
    id: uuid.UUID
    status: str


class AnalysisArtifactOut(BaseModel):
    """RF-041/RF-042. `spec` es la especificacion de grafico que consume un
    frontend con Recharts - nunca una imagen. `source_sql` es la
    trazabilidad hacia la consulta que produjo los datos graficados."""

    id: uuid.UUID
    type: str
    spec: dict[str, Any]
    source_sql: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ToolCallAuditOut(BaseModel):
    """RF-052: fila de la vista agregada Owner/Admin de tool calls de toda
    la organizacion (GET /analyses/tool-calls). A diferencia de ToolCallOut
    (usado dentro del detalle de UN analysis, RF-024), nunca expone
    `input_json` crudo -- ese puede llevar valores literales de la
    pregunta del usuario dentro del SQL generado. Se expone `input_hash`
    (ya calculado y persistido por _record_tool_call en tools.py) como
    referencia estable, igual que hace la auditoria de audit_events."""

    id: uuid.UUID
    tool: str
    status: str
    duration_ms: int
    input_hash: str
    error_message: str | None
    created_at: datetime
    analysis_id: uuid.UUID
    user_id: uuid.UUID

    model_config = {"from_attributes": True}


class AnalysisOut(BaseModel):
    id: uuid.UUID
    dataset_id: uuid.UUID
    question: str
    status: AnalysisStatus
    answer: str | None
    result: list[dict[str, Any]] | None
    error: str | None
    created_at: datetime
    tool_calls: list[ToolCallOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}
