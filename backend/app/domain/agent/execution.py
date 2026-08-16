from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import settings


class SqlExecutionError(Exception):
    """Error de Postgres al ejecutar SQL ya validado (permisos, timeout, etc.)."""


@dataclass
class SqlExecutionResult:
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool


@lru_cache
def get_agent_engine() -> AsyncEngine:
    """Engine separado del de la plataforma (app.db.session.engine), usando
    AGENT_DATABASE_URL - el rol `agent_readonly` (RF-030), sin permisos
    sobre las tablas de negocio. Nunca se comparte con el ORM de la app.
    """
    return create_async_engine(settings.agent_database_url, pool_pre_ping=True)


async def execute_readonly_query(sql: str, *, max_rows: int) -> SqlExecutionResult:
    """Ejecuta `sql` (ya validado por sql_validator, con LIMIT max_rows+1 ya
    incluido) contra la conexion de solo lectura, con statement_timeout
    (RF-032) aplicado a nivel de Postgres, no solo como timeout de Python.
    """
    engine = get_agent_engine()
    timeout_ms = settings.agent_sql_timeout_seconds * 1000

    try:
        async with engine.connect() as conn:
            await conn.execute(text(f"SET statement_timeout = {timeout_ms}"))
            result = await conn.execute(text(sql))
            columns = list(result.keys())
            all_rows = [list(row) for row in result.fetchall()]
    except Exception as exc:  # noqa: BLE001 - cualquier error de Postgres es un fallo de ejecucion
        raise SqlExecutionError(str(exc)) from exc

    truncated = len(all_rows) > max_rows
    rows = all_rows[:max_rows]

    return SqlExecutionResult(columns=columns, rows=rows, row_count=len(rows), truncated=truncated)
