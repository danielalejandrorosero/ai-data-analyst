import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.core.arq_pool import get_arq_pool
from app.core.redis_client import redis_client
from app.db.models.agent_run import AgentRun
from app.db.models.analysis import TERMINAL_ANALYSIS_STATUSES, Analysis
from app.db.models.analysis_artifact import AnalysisArtifact
from app.db.models.membership import Role
from app.db.models.tool_call import ToolCall
from app.db.models.user import User
from app.db.session import get_db
from app.domain.agent.cancellation import CancellationError, cancel_analysis_job
from app.domain.agent.export import ExportError, build_export_payload, rows_to_csv, rows_to_json
from app.domain.agent.schemas import (
    AnalysisArtifactOut,
    AnalysisCancelOut,
    AnalysisCreateRequest,
    AnalysisListItemOut,
    AnalysisOut,
    ToolCallOut,
)
from app.domain.auth import service as auth_service
from app.domain.auth.dependencies import get_current_user
from app.domain.datasets import service as datasets_service

router = APIRouter(prefix="/analyses", tags=["analyses"])


async def _get_visible_analysis(
    db: AsyncSession, *, analysis_id: uuid.UUID, current_user: User
) -> Analysis:
    """Lookup + chequeo de membership compartido por todos los endpoints de
    detalle de un analysis (GET/{id}, cancel, events, artifacts, export) -
    404 uniforme tanto si no existe como si es de otro tenant (RF-003)."""
    result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
    analysis = result.scalar_one_or_none()
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analisis no encontrado")

    membership = await auth_service.get_membership(
        db, user_id=current_user.id, organization_id=analysis.organization_id
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analisis no encontrado")

    return analysis


async def _build_analysis_out(db: AsyncSession, analysis: Analysis) -> AnalysisOut:
    tool_calls_result = await db.execute(
        select(ToolCall)
        .join(AgentRun, ToolCall.agent_run_id == AgentRun.id)
        .where(AgentRun.analysis_id == analysis.id)
        .order_by(ToolCall.created_at)
    )
    tool_calls = [
        ToolCallOut(
            tool=tc.tool,
            status=tc.status,
            duration_ms=tc.duration_ms,
            output_summary=tc.output_summary,
            error_message=tc.error_message,
        )
        for tc in tool_calls_result.scalars()
    ]
    return AnalysisOut(
        id=analysis.id,
        dataset_id=analysis.dataset_id,
        question=analysis.question,
        status=analysis.status,
        answer=analysis.answer,
        result=analysis.result_json,
        error=analysis.error,
        created_at=analysis.created_at,
        tool_calls=tool_calls,
    )


@router.post("", response_model=AnalysisOut, status_code=status.HTTP_202_ACCEPTED)
async def create_analysis(
    payload: AnalysisCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AnalysisOut:
    """RF-020/RF-025 (Fase 4): encola el analisis como job de workers/ (ARQ)
    y responde de inmediato en QUEUED - no espera a que termine. El cliente
    seguiga el progreso via GET /analyses/{id} (polling) o
    GET /analyses/{id}/events (SSE)."""
    dataset = await datasets_service.get_dataset_by_id(db, payload.dataset_id)
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset no encontrado")

    membership = await auth_service.get_membership(
        db, user_id=current_user.id, organization_id=dataset.organization_id
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset no encontrado")
    if membership.role not in (Role.OWNER, Role.ADMIN, Role.ANALYST):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")

    analysis = Analysis(
        organization_id=dataset.organization_id,
        user_id=current_user.id,
        dataset_id=dataset.id,
        question=payload.question,
    )
    db.add(analysis)
    await db.flush()

    pool = await get_arq_pool()
    job = await pool.enqueue_job("run_analysis_job", str(analysis.id))
    analysis.arq_job_id = job.job_id
    await db.commit()

    return await _build_analysis_out(db, analysis)


@router.get("", response_model=list[AnalysisListItemOut])
async def list_analyses(
    organization_id: Annotated[uuid.UUID, Query()],
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[AnalysisListItemOut]:
    """CU-08 (consultar historial). `organization_id` es un parametro que el
    caller ya conoce explicitamente, asi que el rechazo es 403 (no 404) -
    mismo criterio que GET /datasets."""
    membership = await auth_service.get_membership(
        db, user_id=current_user.id, organization_id=organization_id
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")

    result = await db.execute(
        select(Analysis)
        .where(Analysis.organization_id == organization_id)
        .order_by(Analysis.created_at.desc())
    )
    return [AnalysisListItemOut.model_validate(analysis) for analysis in result.scalars()]


@router.get("/{analysis_id}", response_model=AnalysisOut)
async def get_analysis(
    analysis_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AnalysisOut:
    analysis = await _get_visible_analysis(db, analysis_id=analysis_id, current_user=current_user)
    return await _build_analysis_out(db, analysis)


@router.post("/{analysis_id}/cancel", response_model=AnalysisCancelOut)
async def cancel_analysis(
    analysis_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AnalysisCancelOut:
    """RF-025: pide a ARQ que aborte el job en curso (logica real en
    domain/agent/cancellation.py - el router solo valida y traduce a
    HTTP). No espera una confirmacion definitiva del worker - el cliente
    ve el estado real via GET /analyses/{id} o el stream de eventos."""
    analysis = await _get_visible_analysis(db, analysis_id=analysis_id, current_user=current_user)
    membership = await auth_service.get_membership(
        db, user_id=current_user.id, organization_id=analysis.organization_id
    )
    if membership.role not in (Role.OWNER, Role.ADMIN, Role.ANALYST):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")

    if analysis.status in TERMINAL_ANALYSIS_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El analisis ya esta en un estado terminal ({analysis.status.value})",
        )

    pool = await get_arq_pool()
    try:
        await cancel_analysis_job(db, analysis=analysis, pool=pool)
    except CancellationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return AnalysisCancelOut(id=analysis.id, status="cancel_requested")


@router.get("/{analysis_id}/events")
async def stream_analysis_events(
    analysis_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> EventSourceResponse:
    """CU-06 (inspeccionar ejecucion): progreso en vivo por SSE, best-effort
    (Postgres via GET /analyses/{id} sigue siendo la fuente de verdad - ver
    domain/agent/events.py). Si el analysis ya esta en un estado terminal
    al conectarse, se manda ese unico evento y se cierra."""
    analysis = await _get_visible_analysis(db, analysis_id=analysis_id, current_user=current_user)
    initial_status = analysis.status

    async def _events():
        yield {"event": "status", "data": json.dumps({"status": initial_status.value})}
        if initial_status in TERMINAL_ANALYSIS_STATUSES:
            return

        async with redis_client.pubsub() as pubsub:
            await pubsub.subscribe(f"analysis:{analysis_id}:events")
            async for message in pubsub.listen():
                if await request.is_disconnected():
                    break
                if message["type"] != "message":
                    continue
                payload = json.loads(message["data"])
                yield {"event": payload.get("type", "message"), "data": message["data"]}
                if payload.get("type") == "status" and payload.get("status") in {
                    s.value for s in TERMINAL_ANALYSIS_STATUSES
                }:
                    break

    return EventSourceResponse(_events())


@router.get("/{analysis_id}/artifacts", response_model=list[AnalysisArtifactOut])
async def list_artifacts(
    analysis_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[AnalysisArtifactOut]:
    """RF-041/RF-042: graficos generados por create_chart durante la
    corrida, cada uno con la consulta origen para trazabilidad."""
    analysis = await _get_visible_analysis(db, analysis_id=analysis_id, current_user=current_user)

    result = await db.execute(
        select(AnalysisArtifact)
        .where(AnalysisArtifact.analysis_id == analysis.id)
        .order_by(AnalysisArtifact.created_at)
    )
    return [
        AnalysisArtifactOut(
            id=artifact.id,
            type=artifact.type,
            spec=artifact.spec_json,
            source_sql=artifact.source_sql,
            created_at=artifact.created_at,
        )
        for artifact in result.scalars()
    ]


@router.get("/{analysis_id}/export")
async def export_analysis_result(
    analysis_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    export_format: Annotated[str, Query(alias="format")] = "json",
    query_index: Annotated[int | None, Query()] = None,
) -> Response:
    """RF-043: exporta a CSV o JSON el resultado de una de las consultas del
    analysis (la ultima por defecto - ver query_index). Mismo chequeo de
    membership que el resto de los endpoints de detalle, nunca se
    salta la autorizacion por tratarse de una descarga."""
    if export_format not in ("csv", "json"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="format debe ser 'csv' o 'json'",
        )

    analysis = await _get_visible_analysis(db, analysis_id=analysis_id, current_user=current_user)

    try:
        payload = await build_export_payload(db, analysis=analysis, query_index=query_index)
    except ExportError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    columns, rows = payload.columns, payload.rows
    filename = f"analysis-{analysis.id}.{export_format}"
    if export_format == "csv":
        content, media_type = rows_to_csv(columns, rows), "text/csv"
    else:
        content, media_type = rows_to_json(columns, rows), "application/json"

    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    if payload.truncated:
        # RF-043: comunica el truncamiento fuera del cuerpo del archivo -
        # nunca inyectar texto extra en un CSV/JSON valido.
        headers["X-Result-Truncated"] = "true"

    return Response(content=content, media_type=media_type, headers=headers)
