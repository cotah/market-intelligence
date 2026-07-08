"""Endpoints REST da aplicacao.

A logica de negocio fica nos agentes / pipeline; aqui so orquestramos
acesso ao banco e disparo de tarefas.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import require_control_key, require_read_key
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
@router.get(
    "/opportunities",
    response_model=list[OpportunityListItem],
    dependencies=[Depends(require_read_key)],
)
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


@router.get(
    "/opportunities/{opportunity_id}",
    response_model=OpportunityOut,
    dependencies=[Depends(require_read_key)],
)
async def get_opportunity(
    opportunity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Opportunity:
    opp = await session.get(Opportunity, opportunity_id)
    if opp is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return opp


class IdeaIn(BaseModel):
    """Ideia/produto trazido pelo fundador (modo Ideia)."""

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)


@router.post(
    "/opportunities/from-idea",
    response_model=PipelineActionOut,
    dependencies=[Depends(require_control_key)],
)
async def create_opportunity_from_idea(payload: IdeaIn) -> PipelineActionOut:
    """Modo Ideia: o fundador traz um produto/ideia e a pipeline analisa em cima
    dela (dor, concorrencia, mercado, IA, monetizacao, score, plano), SEM
    descobrir topicos. A compatibilidade com o fundador vira informativa (nao
    descarta). Enfileira no Celery e retorna o task_id."""
    try:
        from workers.pipeline_worker import run_for_idea_task

        task = run_for_idea_task.delay(payload.model_dump())
        return PipelineActionOut(
            ok=True, message="Ideia enfileirada para analise.", task_id=str(task.id)
        )
    except Exception as e:  # noqa: BLE001
        log.error("api.from_idea_failed", error=str(e))
        return PipelineActionOut(ok=False, message=f"Falha ao enfileirar: {e}")


# --------------------------- Founder Profile ----------------------------
@router.get(
    "/founder-profile",
    response_model=FounderProfileSchema,
    dependencies=[Depends(require_read_key)],
)
async def read_founder_profile(
    session: AsyncSession = Depends(get_session),
) -> dict:
    profile = await get_profile(session)
    return profile_to_dict(profile)


@router.put(
    "/founder-profile",
    response_model=FounderProfileSchema,
    dependencies=[Depends(require_control_key)],
)
async def update_founder_profile(
    payload: FounderProfileSchema,
    session: AsyncSession = Depends(get_session),
) -> dict:
    profile = await save_profile(session, payload.model_dump())
    log.info("api.founder_profile.updated")
    return profile_to_dict(profile)


# ------------------------------- Reports --------------------------------
@router.get(
    "/reports/daily",
    response_model=list[DailyReportOut],
    dependencies=[Depends(require_read_key)],
)
async def list_daily_reports(
    session: AsyncSession = Depends(get_session),
    limit: int = Query(default=30, ge=1, le=365),
) -> list[DailyReport]:
    stmt = select(DailyReport).order_by(desc(DailyReport.report_date)).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.get(
    "/reports/daily/latest",
    response_model=DailyReportOut,
    dependencies=[Depends(require_read_key)],
)
async def latest_daily_report(
    session: AsyncSession = Depends(get_session),
) -> DailyReport:
    stmt = select(DailyReport).order_by(desc(DailyReport.report_date)).limit(1)
    result = await session.execute(stmt)
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=404, detail="No daily report yet")
    return report


@router.post(
    "/reports/daily/generate",
    response_model=PipelineActionOut,
    dependencies=[Depends(require_control_key)],
)
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
@router.post(
    "/pipeline/start",
    response_model=PipelineActionOut,
    dependencies=[Depends(require_control_key)],
)
async def start_pipeline() -> PipelineActionOut:
    """Liga o modo continuo e ja inicia a primeira rodada.

    A partir daqui cada rodada se auto-encadeia (workers.pipeline_worker.
    scheduled_run) ate o Stop. Nao esperamos o Beat para comecar.
    """
    ok = pipeline_control.set_enabled(True)
    if not ok:
        return PipelineActionOut(ok=False, message="Falha ao habilitar (Redis indisponivel).")

    # Dispara a primeira rodada imediatamente; as proximas se auto-encadeiam.
    try:
        from workers.pipeline_worker import scheduled_run

        task = scheduled_run.delay()
        return PipelineActionOut(
            ok=True,
            message="Pipeline ligada em modo continuo. Primeira rodada iniciada.",
            task_id=str(task.id),
        )
    except Exception as e:  # noqa: BLE001
        # O flag ja esta ligado; o watchdog do Beat iniciara a cadeia em breve.
        log.error("api.start_pipeline.enqueue_failed", error=str(e))
        return PipelineActionOut(
            ok=True,
            message="Pipeline ligada, mas nao consegui iniciar a 1a rodada agora (worker offline?). O Beat iniciara em breve.",
        )


@router.post(
    "/pipeline/stop",
    response_model=PipelineActionOut,
    dependencies=[Depends(require_control_key)],
)
async def stop_pipeline() -> PipelineActionOut:
    ok = pipeline_control.set_enabled(False)
    msg = "Pipeline desabilitada." if ok else "Falha ao desabilitar (Redis indisponivel)."
    return PipelineActionOut(ok=ok, message=msg)


@router.get(
    "/pipeline/status",
    response_model=PipelineStatusOut,
    dependencies=[Depends(require_read_key)],
)
async def pipeline_status() -> PipelineStatusOut:
    return PipelineStatusOut(
        enabled=pipeline_control.is_enabled(),
        redis_available=pipeline_control.redis_available(),
        last_run=pipeline_control.get_status() or None,
    )


@router.post(
    "/pipeline/run-once",
    response_model=PipelineActionOut,
    dependencies=[Depends(require_control_key)],
)
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
