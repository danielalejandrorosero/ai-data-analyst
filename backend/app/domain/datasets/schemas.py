import uuid
from datetime import datetime

from pydantic import BaseModel


class ColumnSchema(BaseModel):
    name: str
    type: str


class DatasetOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    source_id: uuid.UUID
    name: str
    row_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class DatasetSchemaOut(BaseModel):
    id: uuid.UUID
    name: str
    row_count: int
    columns: list[ColumnSchema]

    model_config = {"from_attributes": True}
