import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError


class SqlValidationError(Exception):
    """SQL rechazado por el validador (RF-031). El caller debe auditar el
    rechazo, no solo mostrarlo — ver domain/agent/orchestrator.py."""


def validate_readonly_select(
    sql: str,
    *,
    allowed_table: str,
    max_rows: int,
    max_joins: int = 2,
    max_subqueries: int = 3,
) -> str:
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

    if not statement.args.get("from_"):
        # Un SELECT sin FROM (ej. "SELECT pg_sleep(30)", "SELECT version()",
        # "SELECT current_setting('server_version')") no referencia ninguna
        # tabla - el chequeo de `tables`/`disallowed` de abajo se cumple de
        # forma vacua sin haber leido el dataset en absoluto, permitiendo
        # ejecutar cualquier funcion de Postgres accesible por el rol
        # `agent_readonly` (DoS de bajo costo, fingerprinting de la
        # instancia). En este dominio (preguntas de negocio sobre UN
        # dataset) un SELECT legitimo siempre lee de la tabla autorizada.
        raise SqlValidationError(
            "La consulta debe leer de la tabla del dataset (SELECT sin FROM no esta permitido)"
        )

    with_clause = statement.args.get("with_")
    if with_clause is not None and with_clause.args.get("recursive"):
        # Una CTE recursiva puede no referenciar NINGUNA tabla real (su
        # caso base puede ser "SELECT 1", y la parte recursiva solo se
        # auto-referencia) - eso vacia el set `tables` de abajo y hace que
        # la validacion de tabla autorizada (y los limites de
        # _check_complexity, que no cuentan CTEs) se cumplan de forma
        # vacua sin haber leido la tabla del dataset en absoluto. Ademas es
        # el vector canonico de un DoS sin bound (RF-032) que ningun otro
        # chequeo de este validador cubre.
        raise SqlValidationError("WITH RECURSIVE no esta permitido")

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

    _check_complexity(statement, max_joins=max_joins, max_subqueries=max_subqueries)

    _cap_limit(statement, max_rows)

    return statement.sql(dialect="postgres")


def _check_complexity(statement: exp.Select, *, max_joins: int, max_subqueries: int) -> None:
    """RF-032 (limites de complejidad configurables). El validador ya
    restringe la consulta a una unica tabla fisica (mas CTEs), asi que lo
    que queda por acotar es el costo de self-joins y subqueries anidadas."""
    join_count = len(list(statement.find_all(exp.Join)))
    if join_count > max_joins:
        raise SqlValidationError(
            f"La consulta tiene {join_count} JOIN(s), el maximo permitido es {max_joins}"
        )

    subquery_count = len(list(statement.find_all(exp.Subquery)))
    if subquery_count > max_subqueries:
        raise SqlValidationError(
            f"La consulta tiene {subquery_count} subquery(s), "
            f"el maximo permitido es {max_subqueries}"
        )


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
