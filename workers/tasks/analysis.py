import uuid

from app.db.models.analysis import Analysis
from app.db.models.dataset import Dataset
from app.db.session import async_session_maker
from app.domain.agent.orchestrator import run_analysis
from sqlalchemy import select


async def run_analysis_job(ctx: dict, analysis_id: str) -> None:  # noqa: ARG001 - ctx lo exige ARQ
    """Job real de ARQ (RF-020 a RF-025, Fase 4) - reemplaza el placeholder
    `noop`. Delega toda la logica a domain/agent/orchestrator.py (que ya
    deja el Analysis en un estado terminal siempre); esta funcion solo
    resuelve las entidades y las pasa. Si arq cancela este job
    (Job.abort(), ver POST /analyses/{id}/cancel), asyncio.CancelledError
    se propaga desde adentro de run_analysis - se la deja subir tal cual
    despues de que run_analysis ya dejo el Analysis en CANCELLED, para que
    arq registre el job como abortado y no como completado.
    """
    async with async_session_maker() as db:
        analysis = (
            await db.execute(select(Analysis).where(Analysis.id == uuid.UUID(analysis_id)))
        ).scalar_one()
        dataset = (
            await db.execute(select(Dataset).where(Dataset.id == analysis.dataset_id))
        ).scalar_one()
        await run_analysis(db, analysis=analysis, dataset=dataset)
