from functools import lru_cache

from fastembed import TextEmbedding

from app.core.config import settings


@lru_cache(maxsize=1)
def _model() -> TextEmbedding:
    """Carga perezosa y unica por proceso (ADR-0011): la primera llamada
    descarga el modelo ONNX a un cache local; despues es offline. Nunca se
    carga al importar el modulo - la API solo lo necesita para embeber
    consultas de busqueda, y los tests lo reemplazan entero."""
    return TextEmbedding(model_name=settings.embedding_model)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Sincronico y CPU-bound - los callers async lo corren via
    asyncio.to_thread para no bloquear el event loop."""
    return [vector.tolist() for vector in _model().embed(texts)]


def embed_query(query: str) -> list[float]:
    return embed_texts([query])[0]
