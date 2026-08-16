import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError


class SqlValidationError(Exception):
    """SQL rechazado por el validador (RF-031). El caller debe auditar el
    rechazo, no solo mostrarlo — ver domain/agent/orchestrator.py."""


def validate_readonly_select(sql: str, *, allowed_table: str, max_rows: int) -> str:
    """Valida que `sql` sea una unica sentencia SELECT que solo lea de
    `allowed_table` (nombre calificado por schema, ej. "datasets.ds_abc123").

    Implementa en un mismo punto:
    - RF-030 (solo lectura): rechaza cualquier cosa que no sea SELECT.
    - RF-031 (validar antes de enviar al motor): parseo real con sqlglot,
      no una allowlist de texto/regex.
    - RF-003 (aislamiento de tenant) aplicado tambien a nivel SQL: el
      agente no puede referenciar NINGUNA otra tabla, ni siquiera otro
      dataset de la misma organizacion - solo la tabla fisica exacta que
      se le autorizo para esta consulta.
    - RF-032 (limite de filas): el LIMIT queda grabado en el propio SQL
      que se ejecuta (`max_rows + 1`, para que el caller pueda detectar
      truncamiento) - Postgres nunca calcula mas filas de las necesarias,
      en vez de confiar en truncar la respuesta despues de traerla entera.

    Devuelve el SQL re-serializado (no el string original) para que lo
    que se ejecuta sea exactamente lo que el parser entendio, no lo que
    el usuario/LLM escribio.
    """
    stripped = sql.strip()
    if not stripped:
        raise SqlValidationError("La consulta esta vacia")

    # Una sola sentencia: bloquea "statement stacking" (ej. una consulta
    # que parece un SELECT inocente seguida de un DROP separado por ";").
    without_trailing_semicolon = stripped.rstrip(";").strip()
    if ";" in without_trailing_semicolon:
        raise SqlValidationError("Solo se permite una sentencia SQL por consulta")

    try:
        statements = [s for s in sqlglot.parse(without_trailing_semicolon, read="postgres") if s]
    except ParseError as exc:
        raise SqlValidationError(f"SQL invalido: {exc}") from exc

    if len(statements) != 1:
        raise SqlValidationError("Solo se permite una sentencia SQL por consulta")

    statement = statements[0]
    if not isinstance(statement, exp.Select):
        raise SqlValidationError(
            f"Solo se permiten consultas SELECT (recibido: {type(statement).__name__})"
        )

    if statement.args.get("into"):
        raise SqlValidationError("SELECT INTO no esta permitido (crearia una tabla)")

    # Los alias de CTE (WITH x AS (...) SELECT * FROM x) se parsean como
    # exp.Table al referenciarlos en el SELECT externo, pero no son tablas
    # reales - sin excluirlos, cualquier CTE rompe la validacion aunque
    # su subquery interna ya haya sido validada igual.
    cte_names = {cte.alias_or_name.lower() for cte in statement.find_all(exp.CTE)}

    tables = {
        _qualified_table_name(table)
        for table in statement.find_all(exp.Table)
        if not (table.name.lower() in cte_names and not table.db)
    }
    disallowed = tables - {allowed_table.lower()}
    if disallowed:
        raise SqlValidationError(
            f"La consulta referencia tablas no autorizadas: {', '.join(sorted(disallowed))}"
        )

    _cap_limit(statement, max_rows)

    return statement.sql(dialect="postgres")


def _cap_limit(statement: exp.Select, max_rows: int) -> None:
    cap = max_rows + 1
    existing = statement.args.get("limit")
    if existing is not None:
        try:
            existing_value = int(existing.expression.this)
        except (AttributeError, ValueError, TypeError):
            existing_value = None
        if existing_value is not None and existing_value <= cap:
            return
    statement.set("limit", exp.Limit(expression=exp.Literal.number(cap)))


def _qualified_table_name(table: exp.Table) -> str:
    parts = [part for part in (table.db, table.name) if part]
    return ".".join(parts).lower()
