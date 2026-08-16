import json
import time

import pytest
from app.core.config import settings
from app.domain.agent.execution import SqlExecutionError, execute_readonly_query


class TestStatementTimeout:
    async def test_slow_query_is_cancelled_by_postgres_statement_timeout(self, monkeypatch):
        """RF-032/RNF-003: el timeout se aplica a nivel de conexion Postgres
        (SET statement_timeout), no solo como un timeout de Python alrededor
        de la llamada al agente - una consulta lenta debe ser cancelada por
        Postgres mismo, mucho antes de terminar de dormir."""
        monkeypatch.setattr(settings, "agent_sql_timeout_seconds", 1)

        started = time.monotonic()
        with pytest.raises(SqlExecutionError):
            await execute_readonly_query("SELECT pg_sleep(5)", max_rows=10)
        elapsed = time.monotonic() - started

        assert elapsed < 4, (
            "La consulta tardo casi los 5s completos de pg_sleep - "
            "el statement_timeout de Postgres no la esta cancelando"
        )

    async def test_fast_query_within_timeout_succeeds(self, monkeypatch):
        monkeypatch.setattr(settings, "agent_sql_timeout_seconds", 5)

        result = await execute_readonly_query("SELECT 1 AS value", max_rows=10)

        assert result.rows == [[1]]
        assert result.row_count == 1
        assert result.truncated is False


class TestJsonSafeValueConversion:
    async def test_sum_aggregation_returns_json_serializable_float_not_decimal(self):
        """Regresion real: SUM()/AVG() sobre una columna entera devuelve
        `numeric` en Postgres (para evitar overflow), que asyncpg decodifica
        como Decimal - json.dumps no lo serializa. Encontrado probando
        Fase 5 en vivo contra Docker con una agregacion real (rompia
        execute_readonly_sql con un TypeError sin manejar, dejando el
        analysis en FAILED con mensaje generico)."""
        result = await execute_readonly_query(
            "SELECT SUM(x) AS total FROM (VALUES (1), (2), (3)) AS t(x)", max_rows=10
        )
        assert result.rows == [[6.0]]
        json.dumps(result.rows)  # no debe lanzar TypeError

    async def test_date_column_is_serialized_as_isoformat_string(self):
        result = await execute_readonly_query("SELECT DATE '2026-01-15' AS d", max_rows=10)

        assert result.rows == [["2026-01-15"]]
        json.dumps(result.rows)
