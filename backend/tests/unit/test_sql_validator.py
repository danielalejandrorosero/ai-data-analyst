import pytest
from app.domain.agent.sql_validator import SqlValidationError, validate_readonly_select

ALLOWED = "datasets.ds_abc123"


class TestAllowedQueries:
    def test_simple_select(self):
        result = validate_readonly_select(
            "SELECT * FROM datasets.ds_abc123", allowed_table=ALLOWED, max_rows=1000
        )
        assert "datasets.ds_abc123" in result

    def test_select_with_where_and_columns(self):
        validate_readonly_select(
            "SELECT product, units FROM datasets.ds_abc123 WHERE units > 10",
            allowed_table=ALLOWED,
            max_rows=1000,
        )

    def test_aggregation_with_group_by_and_order_by(self):
        validate_readonly_select(
            "SELECT product, SUM(units) AS total FROM datasets.ds_abc123 "
            "GROUP BY product ORDER BY total DESC",
            allowed_table=ALLOWED,
            max_rows=1000,
        )

    def test_cte_referencing_the_allowed_table(self):
        validate_readonly_select(
            "WITH agg AS (SELECT product, SUM(units) AS total FROM datasets.ds_abc123 "
            "GROUP BY product) SELECT * FROM agg ORDER BY total DESC",
            allowed_table=ALLOWED,
            max_rows=1000,
        )

    def test_trailing_semicolon_is_tolerated(self):
        validate_readonly_select(
            "SELECT * FROM datasets.ds_abc123;", allowed_table=ALLOWED, max_rows=1000
        )

    def test_sql_comment_does_not_break_parsing(self):
        validate_readonly_select(
            "SELECT * FROM datasets.ds_abc123 -- solo esta columna\n",
            allowed_table=ALLOWED,
            max_rows=1000,
        )


class TestBlockedStatementTypes:
    @pytest.mark.parametrize(
        "sql",
        [
            "DROP TABLE datasets.ds_abc123",
            "DELETE FROM datasets.ds_abc123",
            "UPDATE datasets.ds_abc123 SET units = 0",
            "INSERT INTO datasets.ds_abc123 (units) VALUES (1)",
            "TRUNCATE datasets.ds_abc123",
            "ALTER TABLE datasets.ds_abc123 ADD COLUMN x INT",
            "GRANT SELECT ON datasets.ds_abc123 TO other_role",
        ],
    )
    def test_non_select_statements_are_rejected(self, sql):
        with pytest.raises(SqlValidationError):
            validate_readonly_select(sql, allowed_table=ALLOWED, max_rows=1000)

    def test_select_into_is_rejected(self):
        with pytest.raises(SqlValidationError, match="INTO"):
            validate_readonly_select(
                "SELECT * INTO new_table FROM datasets.ds_abc123",
                allowed_table=ALLOWED,
                max_rows=1000,
            )


class TestBlockedTenantCrossover:
    def test_referencing_another_dataset_table_is_rejected(self):
        with pytest.raises(SqlValidationError, match="no autorizadas"):
            validate_readonly_select(
                "SELECT * FROM datasets.ds_otro_dataset", allowed_table=ALLOWED, max_rows=1000
            )

    def test_referencing_platform_table_is_rejected(self):
        with pytest.raises(SqlValidationError, match="no autorizadas"):
            validate_readonly_select(
                "SELECT * FROM public.users", allowed_table=ALLOWED, max_rows=1000
            )

    def test_join_pulling_in_a_disallowed_table_is_rejected(self):
        with pytest.raises(SqlValidationError, match="no autorizadas"):
            validate_readonly_select(
                "SELECT * FROM datasets.ds_abc123 JOIN public.users ON true",
                allowed_table=ALLOWED,
                max_rows=1000,
            )

    def test_cte_referencing_a_disallowed_table_is_rejected(self):
        with pytest.raises(SqlValidationError, match="no autorizadas"):
            validate_readonly_select(
                "WITH x AS (SELECT * FROM public.users) SELECT * FROM x",
                allowed_table=ALLOWED,
                max_rows=1000,
            )


class TestStatementStacking:
    def test_two_statements_separated_by_semicolon_are_rejected(self):
        with pytest.raises(SqlValidationError, match="una sentencia"):
            validate_readonly_select(
                "SELECT * FROM datasets.ds_abc123; DROP TABLE datasets.ds_abc123",
                allowed_table=ALLOWED,
                max_rows=1000,
            )


class TestRowLimitCapping:
    def test_query_without_limit_gets_max_rows_plus_one_injected(self):
        result = validate_readonly_select(
            "SELECT * FROM datasets.ds_abc123", allowed_table=ALLOWED, max_rows=10
        )
        assert "LIMIT 11" in result

    def test_existing_limit_smaller_than_max_rows_is_kept(self):
        result = validate_readonly_select(
            "SELECT * FROM datasets.ds_abc123 LIMIT 5", allowed_table=ALLOWED, max_rows=1000
        )
        assert "LIMIT 5" in result

    def test_existing_limit_larger_than_max_rows_is_capped(self):
        result = validate_readonly_select(
            "SELECT * FROM datasets.ds_abc123 LIMIT 999999", allowed_table=ALLOWED, max_rows=10
        )
        assert "LIMIT 11" in result
        assert "999999" not in result


class TestEmptyOrInvalidInput:
    def test_empty_string_is_rejected(self):
        with pytest.raises(SqlValidationError, match="vacia"):
            validate_readonly_select("", allowed_table=ALLOWED, max_rows=1000)

    def test_whitespace_only_is_rejected(self):
        with pytest.raises(SqlValidationError, match="vacia"):
            validate_readonly_select("   ", allowed_table=ALLOWED, max_rows=1000)

    def test_unparseable_garbage_is_rejected(self):
        with pytest.raises(SqlValidationError):
            validate_readonly_select(
                "esto no es sql valido !!!", allowed_table=ALLOWED, max_rows=1000
            )
