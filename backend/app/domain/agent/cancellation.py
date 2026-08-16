import logging

from arq import ArqRedis
from arq.jobs import Job
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.analysis import TERMINAL_ANALYSIS_STATUSES, Analysis, AnalysisStatus

logger = logging.getLogger("app.agent")


class CancellationError(Exception):
    """El analisis no se puede cancelar (sin job asociado, etc.) - el
    caller (router) la traduce a un HTTP 409."""


async def cancel_analysis_job(db: AsyncSession, *, analysis: Analysis, pool: ArqRedis) -> None:
    """RF-025. Le pide a ARQ que aborte el job y, si arq confirma que lo
    abortó, fuerza `Analysis.status = CANCELLED` cuando todavia no está en
    un estado terminal.

    Por que hace falta forzarlo (no alcanza con que orchestrator.py maneje
    asyncio.CancelledError): si arq aborta el job ANTES de que el worker
    llegue a arrancarlo ("aborted before start"), run_analysis() nunca
    corre - nada más deja el Analysis en CANCELLED, quedaria colgado en
    QUEUED para siempre. Confirmado empiricamente contra Docker real.

    `Job.abort()` puede lanzar excepciones (TimeoutError si el polling
    interno supera el timeout, o la excepcion propia del job si terminó
    con un error no relacionado a la cancelacion) - se capturan todas: no
    sabemos con certeza si abortó o no, pero Postgres (via
    GET /analyses/{id}) sigue siendo la fuente de verdad, así que no hace
    falta que este endpoint garantice una respuesta definitiva.
    """
    if analysis.arq_job_id is None:
        raise CancellationError("El analisis no tiene un job asociado")

    job = Job(analysis.arq_job_id, pool)
    try:
        aborted = await job.abort(timeout=2)
    except Exception as exc:  # noqa: BLE001 - cualquier fallo de arq no debe tumbar el endpoint
        logger.warning(
            "cancel_analysis.abort_unconfirmed analysis_id=%s error=%r", analysis.id, exc
        )
        return

    if aborted and analysis.status not in TERMINAL_ANALYSIS_STATUSES:
        analysis.status = AnalysisStatus.CANCELLED
        analysis.error = "Analisis cancelado por el usuario"
        await db.commit()
