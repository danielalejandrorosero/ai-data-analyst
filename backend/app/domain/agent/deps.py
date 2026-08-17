import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.datasets.schemas import ColumnSchema


@dataclass
class AgentDeps:
    """Dependencias inyectadas a cada tool call del agente (RunContext.deps).

    `results` es el canal por el que execute_readonly_sql/run_analysis
    acumulan la evidencia de CADA operacion exitosa de vuelta al
    orquestador (domain/agent/orchestrator.py), para guardarla en
    Analysis.result_json. RF-022: el agente puede ejecutar mas de una
    consulta por pregunta compleja, asi que esto es una lista, no un
    unico resultado que se pisa entre llamadas. Cada entrada esta acotada
    a _EVIDENCE_ROW_CAP filas (tools.py) para no dejar una columna JSONB
    gigante (.claude/rules/database.md).

    `last_full_result` es DISTINTO de `results`: es el resultado COMPLETO
    (hasta max_rows, no acotado a _EVIDENCE_ROW_CAP) de la ultima
    operacion exitosa - el buffer de trabajo del que run_analysis y
    create_chart leen para calcular agregaciones/armar el grafico. Sin
    esto, esas dos tools terminaban operando sobre la MUESTRA de
    persistencia (100 filas) en vez del resultado real de la consulta
    (hasta 5000), dando agregaciones matematicamente incorrectas sin
    ningun indicio de que eran parciales - encontrado en revision de
    seguridad, no en produccion. No se persiste tal cual (efimero, se
    descarta al terminar la corrida) - lo que se persiste sigue siendo la
    version acotada en `results`.
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
    last_full_result: dict[str, Any] | None = field(default=None)
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
    # RNF-021: hasta ahora "llamá a inspect_schema antes de generar SQL"
    # (RF-021) solo era una instruccion del prompt - el modelo podia
    # ignorarla y execute_readonly_sql la ejecutaba igual. Este flag lo
    # convierte en un guard real de software (el backend autoriza, no el
    # modelo decide solo): se pone en True dentro de inspect_schema y
    # execute_readonly_sql lo exige antes de tocar la DB.
    schema_inspected: bool = False
    max_charts_per_run: int = 5
    # Mismo motivo que query_count: reserva sincronica antes de cualquier
    # await, para que create_chart tambien sea atomico frente a tool calls
    # concurrentes del mismo turno.
    chart_count: int = 0
    # RF-063 (search_documents): la tool necesita el tenant para acotar la
    # busqueda documental. Opcional con default None para no romper a los
    # callers/tests previos a Fase 6 - la tool responde ERROR controlado
    # si falta, nunca busca sin tenant.
    organization_id: uuid.UUID | None = None
    max_doc_searches_per_run: int = 3
    doc_search_count: int = 0
