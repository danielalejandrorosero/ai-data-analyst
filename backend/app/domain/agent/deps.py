import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.datasets.schemas import ColumnSchema


@dataclass
class AgentDeps:
    """Dependencias inyectadas a cada tool call del agente (RunContext.deps).

    `results` es el canal por el que execute_readonly_sql acumula la
    evidencia de CADA consulta exitosa de vuelta al orquestador
    (domain/agent/orchestrator.py), para guardarla en Analysis.result_json.
    RF-022: el agente puede ejecutar mas de una consulta por pregunta
    compleja, asi que esto es una lista, no un unico resultado que se
    pisa entre llamadas.
    """

    db: AsyncSession
    analysis_id: uuid.UUID
    agent_run_id: uuid.UUID
    dataset_id: uuid.UUID
    table_name: str  # calificado por schema, ej. "datasets.ds_abc123"
    columns: list[ColumnSchema]
    max_rows: int
    max_joins: int = 2
    max_subqueries: int = 3
    max_queries_per_run: int = 5
    results: list[dict[str, Any]] = field(default_factory=list)
    # Contador separado de `results` (que solo crece con consultas
    # EXITOSAS) - `query_count` cuenta todo intento, incrementado de forma
    # sincronica al entrar a execute_readonly_sql, antes de cualquier
    # `await`. Necesario porque pydantic-ai puede ejecutar varias tool
    # calls del mismo turno en paralelo (default de la API de OpenAI-
    # compatible); si el tope se chequeara contra `len(results)` (que solo
    # se actualiza DESPUES del round-trip a Postgres), llamadas
    # concurrentes verian todas el mismo valor "viejo" y se saltarian el
    # limite - ver tools.py.
    query_count: int = 0
