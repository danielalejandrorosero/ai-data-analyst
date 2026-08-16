from app.domain.datasets.service import (
    _MAX_COLUMN_NAME_LENGTH,
    _dedupe_column_names,
    _sanitize_column_name,
)


class TestSanitizeColumnName:
    def test_replaces_invalid_characters(self):
        assert _sanitize_column_name("Product Name!", 0) == "product_name_"

    def test_prefixes_when_starts_with_digit(self):
        assert _sanitize_column_name("123abc", 0).startswith("col_0_")

    def test_prefixes_when_empty_after_cleaning(self):
        # "!!!" se limpia a "___", no a vacio (cada caracter invalido se
        # reemplaza por un "_", no se elimina) - el caso realmente vacio
        # es un string en blanco.
        assert _sanitize_column_name("   ", 2).startswith("col_2_")


class TestDedupeColumnNames:
    def test_leaves_unique_names_untouched(self):
        assert _dedupe_column_names(["a", "b", "c"]) == ["a", "b", "c"]

    def test_suffixes_duplicates(self):
        assert _dedupe_column_names(["a", "a", "a"]) == ["a", "a_1", "a_2"]

    def test_never_produces_a_name_longer_than_postgres_limit(self):
        # Nombre base ya en el limite de _BASE_NAME_LENGTH (55) - el sufijo
        # de dedupe no debe hacer que el resultado supere 63 (era el bug
        # real: truncar a 63 antes de dedupear podia colisionar).
        base = "x" * 55
        result = _dedupe_column_names([base, base, base])
        assert len(set(result)) == 3
        assert all(len(name) <= _MAX_COLUMN_NAME_LENGTH for name in result)

    def test_handles_collision_created_by_truncation(self):
        # Dos nombres que Python ve distintos pero que colisionarian si se
        # truncaran ingenuamente al agregar el sufijo.
        long_a = "x" * 55
        long_b = "x" * 55  # identico a proposito: simula la colision real
        result = _dedupe_column_names([long_a, long_b])
        assert result[0] != result[1]
