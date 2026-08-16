import uuid
from datetime import datetime

from pydantic import BaseModel

from app.db.models.document import DocumentStatus


class DocumentOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    filename: str
    file_format: str
    size_bytes: int
    status: DocumentStatus
    error: str | None
    chunk_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentSearchResultOut(BaseModel):
    """Un fragmento relevante (RF-062/RF-063), con la referencia al
    documento origen para trazabilidad."""

    document_id: uuid.UUID
    document_filename: str
    chunk_index: int
    content: str
    score: float
