import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, SecretStr


class ColumnSchema(BaseModel):
    name: str
    type: str


class DatasetOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    source_id: uuid.UUID
    source_type: str
    source_extension: str | None
    name: str
    row_count: int
    column_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class DatasetSchemaOut(BaseModel):
    id: uuid.UUID
    name: str
    row_count: int
    columns: list[ColumnSchema]

    model_config = {"from_attributes": True}


class ExternalConnectionCreateRequest(BaseModel):
    """RF-010. `type` solo acepta "postgres" por ahora - MySQL queda
    diferido explicitamente (ver docs/adr/0004-secrets-management.md y
    docs/SRS.md RF-010)."""

    type: Literal["postgres"]
    name: str = Field(min_length=1, max_length=200)
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(ge=1, le=65535)
    database_name: str = Field(min_length=1, max_length=200)
    username: str = Field(min_length=1, max_length=200)
    password: SecretStr = Field(min_length=1)


class ExternalConnectionOut(BaseModel):
    id: uuid.UUID
    type: str
    name: str
    host: str
    port: int
    database_name: str
    username: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
