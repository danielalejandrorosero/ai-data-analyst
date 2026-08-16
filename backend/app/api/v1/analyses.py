import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent_run import AgentRun
from app.db.models.analysis import Analysis
from app.db.models.membership import Role
from app.db.models.tool_call import ToolCall
from app.db.models.user import User
from app.db.session import get_db
from app.domain.agent.orchestrator import run_analysis
from app.domain.agent.schemas import AnalysisCreateRequest, AnalysisOut, ToolCallOut
from app.domain.auth import service as auth_service
from app.domain.auth.dependencies import get_current_user
from app.domain.datasets import service as datasets_service

router = APIRouter(prefix="/analyses", tags=["analyses"])


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


@router.post("", response_model=AnalysisOut, status_code=status.HTTP_201_CREATED)
async def create_analysis(
    payload: AnalysisCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AnalysisOut:
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

    await run_analysis(db, analysis=analysis, dataset=dataset)

    return await _build_analysis_out(db, analysis)


@router.get("/{analysis_id}", response_model=AnalysisOut)
async def get_analysis(
    analysis_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AnalysisOut:
    result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
    analysis = result.scalar_one_or_none()
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analisis no encontrado")

    membership = await auth_service.get_membership(
        db, user_id=current_user.id, organization_id=analysis.organization_id
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analisis no encontrado")

    return await _build_analysis_out(db, analysis)
