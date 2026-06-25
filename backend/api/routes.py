"""Endpoints REST da aplicacao.

A logica de negocio fica nos agentes / pipeline; aqui so orquestramos
acesso ao banco e disparo de tarefas.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import (
    DailyReportOut,
    FounderProfileSchema,
    OpportunityListItem,
    OpportunityOut,
    PipelineActionOut,
    PipelineStatusOut,
)
from core import pipeline_control
from core.database import get_session
from core.founder_profile_service import get_profile, profile_to_dict, save_profile
from core.logging_config import get_logger
from models import DailyReport, Opportunity, OpportunityStatus

log = get_logger("api")

router = APIRouter()


# ----------------------------- Opportunities -----------------------------
@router.get("/opportunities", response_model=list[OpportunityListItem])
async def list_opportunities(
    session: AsyncSession = Depends(get_session),
    score_min: float | None = Query(default=None, ge=0, le=10),
    status: OpportunityStatus | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[Opportunity]:
    stmt = select(Opportunity)
    if score_min is not None:
        stmt = stmt.where(Opportunity.score_total >= score_min)
    if status is not None:
        stmt = stmt.where(Opportunity.status == status)
    stmt = stmt.order_by(desc(Opportunity.created_at)).limit(limit).offset(offset)

    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.get("/opportunities/{opportunity_id}", response_model=OpportunityOut)
async def get_opportunity(
    opportunity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Opportunity:
    opp = await session.get(Opportunity, opportunity_id)
    if opp is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return opp


# --------------------------- Founder Profile ----------------------------
@router.get("/founder-profile", response_model=FounderProfileSchema)
async def read_founder_profile(
    session: AsyncSession = Depends(get_session),
) -> dict:
    profile = await get_profile(session)
    return profile_to_dict(profile)


@router.put("/founder-profile", response_model=FounderProfileSchema)
async def update_founder_profile(
    payload: FounderProfileSchema,
    session: AsyncSession = Depends(get_session),
) -> dict:
    profile = await save_profile(session, payload.model_dump())
    log.info("api.founder_profile.updated")
    return profile_to_dict(profile)


# ------------------------------- Reports --------------------------------
@router.get("/reports/daily", response_model=list[DailyReportOut])
async def list_daily_reports(
    session: AsyncSession = Depends(get_session),
    limit: int = Query(default=30, ge=1, le=365),
) -> list[DailyReport]:
    stmt = select(DailyReport).order_by(desc(DailyReport.report_date)).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.get("/reports/daily/latest", response_model=DailyReportOut)
async def latest_daily_report(
    session: AsyncSession = Depends(get_session),
) -> DailyReport:
    stmt = select(DailyReport).order_by(desc(DailyReport.report_date)).limit(1)
    result = await session.execute(stmt)
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=404, detail="No daily report yet")
    return report


@router.post("/reports/daily/generate", response_model=PipelineActionOut)
async def generate_daily_report() -> PipelineActionOut:
    """Gera o relatorio diario sob demanda (enfileira no Celery)."""
    try:
        from workers.pipeline_worker import generate_daily_report_task

        task = generate_daily_report_task.delay()
        return PipelineActionOut(ok=True, message="Relatorio diario enfileirado.", task_id=str(task.id))
    except Exception as e:  # noqa: BLE001
        log.error("api.daily_report_failed", error=str(e))
        return PipelineActionOut(ok=False, message=f"Falha ao enfileirar: {e}")


# ------------------------------ Pipeline --------------------------------
@router.post("/pipeline/start", response_model=PipelineActionOut)
async def start_pipeline() -> PipelineActionOut:
    ok = pipeline_control.set_enabled(True)
    msg = "Pipeline habilitada." if ok else "Falha ao habilitar (Redis indisponivel)."
    return PipelineActionOut(ok=ok, message=msg)


@router.post("/pipeline/stop", response_model=PipelineActionOut)
async def stop_pipeline() -> PipelineActionOut:
    ok = pipeline_control.set_enabled(False)
    msg = "Pipeline desabilitada." if ok else "Falha ao desabilitar (Redis indisponivel)."
    return PipelineActionOut(ok=ok, message=msg)


@router.get("/pipeline/status", response_model=PipelineStatusOut)
async def pipeline_status() -> PipelineStatusOut:
    return PipelineStatusOut(
        enabled=pipeline_control.is_enabled(),
        redis_available=pipeline_control.redis_available(),
        last_run=pipeline_control.get_status() or None,
    )


@router.post("/pipeline/run-once", response_model=PipelineActionOut)
async def run_pipeline_once() -> PipelineActionOut:
    """Enfileira uma rodada unica no Celery e retorna o id da tarefa.

    Requer o worker Celery rodando. Se o broker estiver fora, retorna erro claro.
    """
    try:
        from workers.pipeline_worker import run_pipeline_once_task

        task = run_pipeline_once_task.delay()
        return PipelineActionOut(ok=True, message="Rodada enfileirada.", task_id=str(task.id))
    except Exception as e:  # noqa: BLE001
        log.error("api.run_once_failed", error=str(e))
        return PipelineActionOut(ok=False, message=f"Falha ao enfileirar: {e}")
