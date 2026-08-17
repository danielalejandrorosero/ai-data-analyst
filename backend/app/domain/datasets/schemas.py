import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, SecretStr


class ColumnSchema(BaseModel):
    name: str
    type: str
    # RF-013: anotacion semantica opcional de la columna (texto libre,
    # asignada por el usuario) - el agente la ve al inspeccionar el
    # esquema (domain/agent/tools.py::inspect_schema) para mejorar su
    # contexto sobre que significa la columna.
    description: str | None = None


class DatasetOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    source_id: uuid.UUID
    source_type: str
    source_extension: str | None
    name: str
    description: str | None = None
    row_count: int
    column_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class DatasetSchemaOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    row_count: int
    columns: list[ColumnSchema]

    model_config = {"from_attributes": True}


class DatasetAnnotationUpdate(BaseModel):
    """RF-013. `column_descriptions` solo actualiza las columnas
    presentes en el dict (matcheadas por `name` dentro de schema_json) -
    las que no vengan no se tocan."""

    description: str | None = None
    column_descriptions: dict[str, str] | None = None


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
