import asyncio
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.document import Document, DocumentChunk, DocumentStatus
from app.domain.documents import embeddings
from app.domain.documents.schemas import DocumentSearchResultOut

# Constante estandar de Reciprocal Rank Fusion (el paper original usa 60):
# amortigua la diferencia entre rankings para que un resultado que aparece
# en AMBAS listas (semantica y lexica) suba por encima de uno que domina
# solo una.
_RRF_K = 60


def _base_query(organization_id: uuid.UUID):
    """JOIN al documento padre: ahi ocurre el filtro de tenant (RF-062) y
    el de estado - un documento FAILED o aun PROCESSING no aparece nunca
    en resultados."""
    return (
        select(DocumentChunk, Document)
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(
            Document.organization_id == organization_id,
            Document.status == DocumentStatus.READY,
        )
    )


async def hybrid_search(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    query: str,
    top_k: int | None = None,
) -> list[DocumentSearchResultOut]:
    """RF-062: top-k semantico (coseno en pgvector) + top-k lexico
    (full-text de Postgres), fusionados con RRF."""
    limit = top_k or settings.document_search_top_k

    query_vector = await asyncio.to_thread(embeddings.embed_query, query)
    semantic_rows = (
        await db.execute(
            _base_query(organization_id)
            .order_by(DocumentChunk.embedding.cosine_distance(query_vector))
            .limit(limit)
        )
    ).all()

    tsquery = func.websearch_to_tsquery("spanish", query)
    lexical_rows = (
        await db.execute(
            _base_query(organization_id)
            .where(func.to_tsvector("spanish", DocumentChunk.content).op("@@")(tsquery))
            .order_by(
                func.ts_rank(func.to_tsvector("spanish", DocumentChunk.content), tsquery).desc()
            )
            .limit(limit)
        )
    ).all()

    scores: dict[uuid.UUID, float] = {}
    entries: dict[uuid.UUID, tuple[DocumentChunk, Document]] = {}
    for rows in (semantic_rows, lexical_rows):
        for rank, (chunk, document) in enumerate(rows):
            scores[chunk.id] = scores.get(chunk.id, 0.0) + 1.0 / (_RRF_K + rank + 1)
            entries[chunk.id] = (chunk, document)

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:limit]
    return [
        DocumentSearchResultOut(
            document_id=entries[chunk_id][1].id,
            document_filename=entries[chunk_id][1].filename,
            chunk_index=entries[chunk_id][0].chunk_index,
            content=entries[chunk_id][0].content,
            score=round(score, 6),
        )
        for chunk_id, score in ranked
    ]
