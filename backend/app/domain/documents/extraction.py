import io

from docx import Document as DocxDocument
from pypdf import PdfReader

SUPPORTED_FORMATS = {"pdf", "txt", "md", "docx"}


class TextExtractionError(Exception):
    """Contenido ilegible o vacio para el formato declarado (RF-060/RF-061)."""


def extract_text(content: bytes, file_format: str) -> str:
    """Extrae texto plano segun el formato (RF-061). PDF sin OCR: solo
    texto embebido - un PDF escaneado sale vacio y se reporta como error
    explicito, no como documento READY sin contenido."""
    if file_format == "pdf":
        try:
            reader = PdfReader(io.BytesIO(content))
            text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            raise TextExtractionError(f"No se pudo leer el PDF: {exc}") from exc
    elif file_format == "docx":
        try:
            docx = DocxDocument(io.BytesIO(content))
            text = "\n\n".join(p.text for p in docx.paragraphs)
        except Exception as exc:
            raise TextExtractionError(f"No se pudo leer el DOCX: {exc}") from exc
    elif file_format in ("txt", "md"):
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("latin-1", errors="replace")
    else:
        raise TextExtractionError(f"Formato no soportado: {file_format}")

    if not text.strip():
        raise TextExtractionError(
            "El documento no contiene texto extraible "
            "(si es un PDF escaneado, no hay soporte de OCR en el MVP)"
        )
    return text


def chunk_text(text: str, *, max_chars: int, overlap: int) -> list[str]:
    """Ventana deslizante con preferencia por cortar en salto de linea o
    espacio - suficiente para retrieval (los limites exactos de fragmento
    no afectan la busqueda hibrida de forma material a esta escala)."""
    normalized = text.strip()
    chunks: list[str] = []
    start = 0
    length = len(normalized)

    while start < length:
        end = min(start + max_chars, length)
        if end < length:
            boundary = normalized.rfind("\n", start, end)
            if boundary <= start:
                boundary = normalized.rfind(" ", start, end)
            if boundary > start + max_chars // 2:
                end = boundary
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= length:
            break
        start = max(end - overlap, start + 1)

    return chunks
