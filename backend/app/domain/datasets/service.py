import io
import re
import uuid

import polars as pl
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.schema import CreateSchema, CreateTable

from app.core.config import settings
from app.db.models.data_source import DataSource
from app.db.models.dataset import Dataset
from app.domain.audit import service as audit_service
from app.domain.datasets.schemas import ColumnSchema, DatasetSchemaOut
from app.domain.datasets.type_mapping import polars_dtype_to_catalog_type, polars_dtype_to_sa_type

DATASET_SCHEMA_NAME = "datasets"
ALLOWED_EXTENSIONS = (".csv", ".xlsx")

_COLUMN_NAME_RE = re.compile(r"[^a-zA-Z0-9_]")


class DatasetImportError(Exception):
    """Error de negocio al importar (archivo invalido, muy grande, no parsea, etc.)."""


# Postgres trunca identificadores a 63 bytes (NAMEDATALEN=64) en silencio.
# El nombre base se acota mas corto para dejar lugar al sufijo numerico que
# _dedupe_column_names pueda necesitar agregar - si se truncara a 63 antes
# de dedupear, dos columnas "distintas" para Python podrian colisionar en
# el mismo identificador fisico sin que nadie se entere.
_MAX_COLUMN_NAME_LENGTH = 63
_BASE_NAME_LENGTH = 55


def _sanitize_column_name(name: str, index: int) -> str:
    cleaned = _COLUMN_NAME_RE.sub("_", name.strip())
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"col_{index}_{cleaned}"
    return cleaned.lower()[:_BASE_NAME_LENGTH]


def _dedupe_column_names(names: list[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for name in names:
        candidate = name
        suffix = 0
        while candidate in seen:
            suffix += 1
            candidate = f"{name}_{suffix}"[:_MAX_COLUMN_NAME_LENGTH]
        seen.add(candidate)
        result.append(candidate)
    return result


def _read_dataframe(filename_lower: str, content: bytes) -> pl.DataFrame:
    buffer = io.BytesIO(content)
    try:
        if filename_lower.endswith(".csv"):
            return pl.read_csv(buffer)
        return pl.read_excel(buffer)
    except Exception as exc:  # noqa: BLE001 - cualquier error de parseo es un error de negocio
        raise DatasetImportError(f"No se pudo parsear el archivo: {exc}") from exc


async def _get_or_create_upload_source(db: AsyncSession, organization_id: uuid.UUID) -> DataSource:
    result = await db.execute(
        select(DataSource).where(
            DataSource.organization_id == organization_id, DataSource.type == "upload"
        )
    )
    source = result.scalar_one_or_none()
    if source is not None:
        return source

    # ON CONFLICT DO NOTHING contra uq_data_source_org_type: dos imports
    # concurrentes del primer dataset de una organizacion nueva no pueden
    # crear dos filas "upload" (select-then-insert sin esto es una
    # condicion de carrera real, no solo teorica).
    insert_stmt = (
        pg_insert(DataSource)
        .values(organization_id=organization_id, type="upload", status="active")
        .on_conflict_do_nothing(constraint="uq_data_source_org_type")
    )
    await db.execute(insert_stmt)

    result = await db.execute(
        select(DataSource).where(
            DataSource.organization_id == organization_id, DataSource.type == "upload"
        )
    )
    return result.scalar_one()


async def import_file(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    filename: str,
    content: bytes,
    dataset_name: str | None,
) -> DatasetSchemaOut:
    lower = filename.lower()
    if not lower.endswith(ALLOWED_EXTENSIONS):
        raise DatasetImportError("Solo se aceptan archivos .csv o .xlsx")

    max_bytes = settings.import_max_file_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise DatasetImportError(
            f"El archivo supera el limite de {settings.import_max_file_size_mb}MB"
        )

    if lower.endswith(".csv") and b"\x00" in content:
        # CSV es un formato de texto laxo: Polars "parsea" casi cualquier
        # contenido, incluido binario, como una fila/columna valida. Un
        # byte nulo es un indicador barato y confiable de que esto no es
        # texto real (defensa contra carga maliciosa de archivo, ver
        # docs/security/threat-model.md).
        raise DatasetImportError("El archivo no parece ser un CSV de texto valido")

    df = _read_dataframe(lower, content)

    if df.height > settings.import_max_rows:
        raise DatasetImportError(f"El archivo supera el limite de {settings.import_max_rows} filas")

    sanitized_names = _dedupe_column_names(
        [_sanitize_column_name(name, i) for i, name in enumerate(df.columns)]
    )
    df.columns = sanitized_names

    columns_schema = [
        ColumnSchema(name=name, type=polars_dtype_to_catalog_type(dtype))
        for name, dtype in zip(df.columns, df.dtypes, strict=True)
    ]

    source = await _get_or_create_upload_source(db, organization_id)

    dataset_id = uuid.uuid4()
    table_name = f"ds_{dataset_id.hex}"

    metadata = sa.MetaData(schema=DATASET_SCHEMA_NAME)
    table = sa.Table(
        table_name,
        metadata,
        *[
            sa.Column(name, polars_dtype_to_sa_type(dtype))
            for name, dtype in zip(df.columns, df.dtypes, strict=True)
        ],
    )

    conn = await db.connection()
    await conn.execute(CreateSchema(DATASET_SCHEMA_NAME, if_not_exists=True))
    await conn.execute(CreateTable(table))

    records = df.to_dicts()
    if records:
        await conn.execute(table.insert(), records)

    dataset = Dataset(
        id=dataset_id,
        organization_id=organization_id,
        source_id=source.id,
        name=dataset_name or filename.rsplit(".", 1)[0],
        table_name=table_name,
        row_count=df.height,
        schema_json=[column.model_dump() for column in columns_schema],
    )
    db.add(dataset)
    await db.flush()

    await audit_service.record_event(
        db,
        organization_id=organization_id,
        actor_id=actor_id,
        action="dataset.import",
        target=f"dataset:{dataset.id}",
    )
    await db.commit()

    return DatasetSchemaOut(
        id=dataset.id, name=dataset.name, row_count=dataset.row_count, columns=columns_schema
    )


async def list_datasets(db: AsyncSession, *, organization_id: uuid.UUID) -> list[Dataset]:
    result = await db.execute(
        select(Dataset)
        .where(Dataset.organization_id == organization_id)
        .order_by(Dataset.created_at.desc())
    )
    return list(result.scalars())


async def get_dataset_by_id(db: AsyncSession, dataset_id: uuid.UUID) -> Dataset | None:
    """Busca el dataset solo por id, sin filtrar por organization_id.

    El caller (router) es responsable de verificar membership en
    `dataset.organization_id` antes de exponer nada — separar la busqueda
    de la autorizacion permite devolver el mismo 404 tanto si el dataset
    no existe como si existe pero es de otra organizacion, sin filtrar
    cual de los dos casos es (RF-003).
    """
    result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
    return result.scalar_one_or_none()


def build_dataset_schema_out(dataset: Dataset) -> DatasetSchemaOut:
    return DatasetSchemaOut(
        id=dataset.id,
        name=dataset.name,
        row_count=dataset.row_count,
        columns=[ColumnSchema(**column) for column in dataset.schema_json],
    )
