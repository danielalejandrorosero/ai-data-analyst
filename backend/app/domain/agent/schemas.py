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


class AnalysisOut(BaseModel):
    id: uuid.UUID
    dataset_id: uuid.UUID
    question: str
    status: AnalysisStatus
    answer: str | None
    result: dict[str, Any] | None
    error: str | None
    created_at: datetime
    tool_calls: list[ToolCallOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}
