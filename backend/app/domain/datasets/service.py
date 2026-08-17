import io
import re
import uuid
from datetime import UTC, datetime

import polars as pl
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession
from sqlalchemy.schema import CreateSchema, CreateTable, DropTable

from app.core.config import settings
from app.db.models.data_source import DataSource
from app.db.models.dataset import Dataset
from app.domain.audit import service as audit_service
from app.domain.datasets.schemas import ColumnSchema, DatasetAnnotationUpdate, DatasetSchemaOut
from app.domain.datasets.type_mapping import polars_dtype_to_catalog_type, polars_dtype_to_sa_type

DATASET_SCHEMA_NAME = "datasets"
ALLOWED_EXTENSIONS = (".csv", ".xlsx")

_COLUMN_NAME_RE = re.compile(r"[^a-zA-Z0-9_]")


class DatasetImportError(Exception):
    """Error de negocio al importar (archivo invalido, muy grande, no parsea, etc.)."""


async def _grant_agent_readonly_select(conn: AsyncConnection, table_name: str) -> None:
    """RF-030 / docs/security/threat-model.md ("Aislamiento de tenant en el
    schema datasets es de una sola capa"): el rol agent_readonly ya NO
    recibe SELECT automatico via ALTER DEFAULT PRIVILEGES (ver
    infrastructure/postgres/init/002-agent-readonly-role.sh) - cada tabla
    fisica nueva necesita este GRANT explicito, ejecutado con la conexion
    de PLATAFORMA (duena de la tabla recien creada), nunca con la
    conexion agent_readonly (que es de solo lectura y no puede otorgar
    permisos). `table_name` siempre es `ds_<uuid.hex>` (generado
    server-side, nunca desde input externo) - seguro de interpolar."""
    await conn.execute(
        sa.text(f'GRANT SELECT ON {DATASET_SCHEMA_NAME}."{table_name}" TO agent_readonly')
    )


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


def _parse_dataset_file(
    filename: str, content: bytes
) -> tuple[pl.DataFrame, list[ColumnSchema], str]:
    """Parseo + validacion compartidos entre `import_file` (RF-011) y
    `reimport_file` (RF-014): valida extension/tamano/filas, sanitiza
    nombres de columna y devuelve el DataFrame ya con columnas renombradas,
    su schema de catalogo inferido y la extension normalizada (sin punto).
    """
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

    return df, columns_schema, lower.rsplit(".", 1)[1]


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
    df, columns_schema, extension = _parse_dataset_file(filename, content)

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
    await _grant_agent_readonly_select(conn, table_name)

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
        source_extension=extension,
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


async def list_datasets(
    db: AsyncSession, *, organization_id: uuid.UUID
) -> list[tuple[Dataset, str]]:
    """Devuelve cada dataset junto al `type` de su DataSource ("upload" o
    "postgres") - Dataset no tiene esa columna, y el catalogo (RF-012)
    necesita mostrarla sin que el cliente tenga que resolverla aparte."""
    result = await db.execute(
        select(Dataset, DataSource.type)
        .join(DataSource, Dataset.source_id == DataSource.id)
        .where(Dataset.organization_id == organization_id)
        .order_by(Dataset.created_at.desc())
    )
    return list(result.all())


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
        description=dataset.description,
        row_count=dataset.row_count,
        columns=[ColumnSchema(**column) for column in dataset.schema_json],
    )


async def update_dataset_annotations(
    db: AsyncSession, *, dataset: Dataset, payload: DatasetAnnotationUpdate, actor_id: uuid.UUID
) -> Dataset:
    """RF-013: actualiza la descripcion del dataset y/o de columnas
    puntuales de su schema_json. Solo toca lo que viene en el payload -
    `description=None` en el payload significa "no tocar", no "borrar"
    (mismo criterio que `column_descriptions=None`)."""
    if payload.description is not None:
        dataset.description = payload.description

    if payload.column_descriptions:
        updated_columns = []
        for column in dataset.schema_json:
            new_description = payload.column_descriptions.get(column["name"])
            if new_description is not None:
                updated_columns.append({**column, "description": new_description})
            else:
                updated_columns.append(column)
        # Reasignacion completa (no mutacion in-place del dict existente)
        # para que SQLAlchemy detecte el cambio en la columna JSONB - ver
        # comentario del modelo en db/models/dataset.py.
        dataset.schema_json = updated_columns

    await audit_service.record_event(
        db,
        organization_id=dataset.organization_id,
        actor_id=actor_id,
        action="dataset.annotate",
        target=f"dataset:{dataset.id}",
    )
    await db.commit()
    await db.refresh(dataset)
    return dataset


def _diff_schema(
    old_columns: list[dict], new_columns: list[ColumnSchema]
) -> tuple[list[str], list[str], list[dict[str, str]]]:
    """RF-014: compara el `schema_json` viejo contra el nuevo schema
    inferido y devuelve (added, removed, type_changed) por nombre de
    columna. Una columna que cambia de posicion pero no de nombre/tipo no
    cuenta como cambio."""
    old_by_name = {column["name"]: column for column in old_columns}
    new_by_name = {column.name: column for column in new_columns}

    added = [name for name in new_by_name if name not in old_by_name]
    removed = [name for name in old_by_name if name not in new_by_name]
    type_changed = [
        {"column": name, "from": old_by_name[name]["type"], "to": new_by_name[name].type}
        for name in new_by_name
        if name in old_by_name and old_by_name[name]["type"] != new_by_name[name].type
    ]
    return added, removed, type_changed


async def reimport_file(
    db: AsyncSession,
    *,
    dataset: Dataset,
    actor_id: uuid.UUID,
    filename: str,
    content: bytes,
) -> DatasetSchemaOut:
    """RF-014: reemplaza el contenido de un dataset EXISTENTE con un
    archivo nuevo - no crea un dataset nuevo, reusa `dataset.table_name`.
    Detecta el cambio de esquema contra `dataset.schema_json` y preserva
    las `description` de columnas que sobreviven con el mismo nombre.
    """
    df, new_columns_schema, extension = _parse_dataset_file(filename, content)

    old_columns = dataset.schema_json
    added, removed, type_changed = _diff_schema(old_columns, new_columns_schema)

    old_descriptions = {column["name"]: column.get("description") for column in old_columns}
    final_columns = [
        ColumnSchema(
            name=column.name,
            type=column.type,
            description=old_descriptions.get(column.name),
        )
        for column in new_columns_schema
    ]

    metadata = sa.MetaData(schema=DATASET_SCHEMA_NAME)
    table = sa.Table(
        dataset.table_name,
        metadata,
        *[
            sa.Column(name, polars_dtype_to_sa_type(dtype))
            for name, dtype in zip(df.columns, df.dtypes, strict=True)
        ],
    )

    # DROP + CREATE + INSERT + update de catalogo, todo en la misma
    # transaccion de la sesion (DDL transaccional en Postgres) - si algo
    # falla a mitad de camino, `get_db` hace rollback de todo junto y el
    # dataset no queda en un estado inconsistente (tabla vieja borrada
    # pero catalogo sin actualizar, o viceversa).
    conn = await db.connection()
    await conn.execute(DropTable(table, if_exists=True))
    await conn.execute(CreateTable(table))
    # DROP TABLE se lleva el GRANT anterior con la tabla vieja - hay que
    # re-otorgarlo sobre la tabla recreada, igual que en import_file.
    await _grant_agent_readonly_select(conn, dataset.table_name)

    records = df.to_dicts()
    if records:
        await conn.execute(table.insert(), records)

    dataset.schema_json = [column.model_dump() for column in final_columns]
    dataset.row_count = df.height
    dataset.source_extension = extension
    dataset.schema_updated_at = datetime.now(UTC)
    dataset.last_schema_change = {
        "added": added,
        "removed": removed,
        "type_changed": type_changed,
    }
    db.add(dataset)
    await db.flush()

    change_summary = (
        f"added={added} removed={removed} type_changed={[c['column'] for c in type_changed]}"
    )
    await audit_service.record_event(
        db,
        organization_id=dataset.organization_id,
        actor_id=actor_id,
        action="dataset.reimport",
        target=f"dataset:{dataset.id} {change_summary}"[:255],
    )
    await db.commit()
    await db.refresh(dataset)

    return DatasetSchemaOut(
        id=dataset.id,
        name=dataset.name,
        description=dataset.description,
        row_count=dataset.row_count,
        columns=final_columns,
    )
