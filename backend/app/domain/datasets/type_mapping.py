import polars as pl
import sqlalchemy as sa

# Mapeo de tipos Polars -> (tipo SQLAlchemy para la tabla fisica, tipo de
# catalogo legible para el schema JSON expuesto en la API). Cualquier
# dtype no listado cae en el fallback de sa.Text/"string" - preferimos
# guardar texto de mas a fallar la importacion por un tipo no mapeado.
_TYPE_MAP: dict[type, tuple[type[sa.types.TypeEngine], str]] = {
    pl.Int8: (sa.BigInteger, "integer"),
    pl.Int16: (sa.BigInteger, "integer"),
    pl.Int32: (sa.BigInteger, "integer"),
    pl.Int64: (sa.BigInteger, "integer"),
    pl.UInt8: (sa.BigInteger, "integer"),
    pl.UInt16: (sa.BigInteger, "integer"),
    pl.UInt32: (sa.BigInteger, "integer"),
    pl.UInt64: (sa.BigInteger, "integer"),
    pl.Float32: (sa.Float, "float"),
    pl.Float64: (sa.Float, "float"),
    pl.Boolean: (sa.Boolean, "boolean"),
    pl.Date: (sa.Date, "date"),
    pl.Datetime: (sa.DateTime(timezone=False), "datetime"),
    pl.Utf8: (sa.Text, "string"),
}


def polars_dtype_to_sa_type(dtype: pl.DataType) -> sa.types.TypeEngine:
    sa_type, _ = _TYPE_MAP.get(type(dtype), (sa.Text, "string"))
    return sa_type()


def polars_dtype_to_catalog_type(dtype: pl.DataType) -> str:
    _, catalog_type = _TYPE_MAP.get(type(dtype), (sa.Text, "string"))
    return catalog_type
