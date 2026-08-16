import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.datasets.schemas import ColumnSchema


@dataclass
class AgentDeps:
    """Dependencias inyectadas a cada tool call del agente (RunContext.deps).

    `last_result` es el canal por el que execute_readonly_sql le pasa la
    evidencia de la ultima consulta exitosa de vuelta al orquestador
    (domain/agent/orchestrator.py), para guardarla en Analysis.result_json.
    """

    db: AsyncSession
    agent_run_id: uuid.UUID
    dataset_id: uuid.UUID
    table_name: str  # calificado por schema, ej. "datasets.ds_abc123"
    columns: list[ColumnSchema]
    max_rows: int
    max_joins: int = 2
    max_subqueries: int = 3
    last_result: dict[str, Any] | None = field(default=None)
