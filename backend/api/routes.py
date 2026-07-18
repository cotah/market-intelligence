"""Endpoints REST da aplicacao.

A logica de negocio fica nos agentes / pipeline; aqui so orquestramos
acesso ao banco e disparo de tarefas.

Multi-tenancy: TODO endpoint exige X-Account-Id (core/tenancy.py).
Sem header => 400. Toda leitura filtra por account_id e toda escrita
carimba o account_id — nunca ha fallback para dado global.
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
    HuntRunOut,
    HuntSettingsIn,
    HuntSettingsOut,
    OpportunityListItem,
    OpportunityOut,
    PipelineActionOut,
    PipelineStatusOut,
)
from core import hunt_service, pipeline_control
from core.database import get_session
from core.founder_profile_service import get_profile, profile_to_dict, save_profile
from core.logging_config import get_logger
from core.tenancy import require_account_id
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
    account_id: uuid.UUID = Depends(require_account_id),
    session: AsyncSession = Depends(get_session),
    score_min: float | None = Query(default=None, ge=0, le=10),
    status: OpportunityStatus | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[Opportunity]:
    stmt = select(Opportunity).where(Opportunity.account_id == account_id)
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
    account_id: uuid.UUID = Depends(require_account_id),
    session: AsyncSession = Depends(get_session),
) -> Opportunity:
    opp = await session.get(Opportunity, opportunity_id)
    # Oportunidade de OUTRA conta => 404 (mesma resposta de "nao existe",
    # para nao revelar a existencia de dados alheios).
    if opp is None or opp.account_id != account_id:
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
async def create_opportunity_from_idea(
    payload: IdeaIn,
    account_id: uuid.UUID = Depends(require_account_id),
) -> PipelineActionOut:
    """Modo Ideia: o fundador traz um produto/ideia e a pipeline analisa em cima
    dela (dor, concorrencia, mercado, IA, monetizacao, score, plano), SEM
    descobrir topicos. A compatibilidade com o fundador vira informativa (nao
    descarta). Enfileira no Celery e retorna o task_id."""
    try:
        from workers.pipeline_worker import run_for_idea_task

        task = run_for_idea_task.delay(payload.model_dump(), account_id=str(account_id))
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
    account_id: uuid.UUID = Depends(require_account_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    profile = await get_profile(session, account_id)
    return profile_to_dict(profile)


@router.put(
    "/founder-profile",
    response_model=FounderProfileSchema,
    dependencies=[Depends(require_control_key)],
)
async def update_founder_profile(
    payload: FounderProfileSchema,
    account_id: uuid.UUID = Depends(require_account_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    profile = await save_profile(session, account_id, payload.model_dump())
    log.info("api.founder_profile.updated", account_id=str(account_id))
    return profile_to_dict(profile)


# ------------------------------- Reports --------------------------------
@router.get(
    "/reports/daily",
    response_model=list[DailyReportOut],
    dependencies=[Depends(require_read_key)],
)
async def list_daily_reports(
    account_id: uuid.UUID = Depends(require_account_id),
    session: AsyncSession = Depends(get_session),
    limit: int = Query(default=30, ge=1, le=365),
) -> list[DailyReport]:
    stmt = (
        select(DailyReport)
        .where(DailyReport.account_id == account_id)
        .order_by(desc(DailyReport.report_date))
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.get(
    "/reports/daily/latest",
    response_model=DailyReportOut,
    dependencies=[Depends(require_read_key)],
)
async def latest_daily_report(
    account_id: uuid.UUID = Depends(require_account_id),
    session: AsyncSession = Depends(get_session),
) -> DailyReport:
    stmt = (
        select(DailyReport)
        .where(DailyReport.account_id == account_id)
        .order_by(desc(DailyReport.report_date))
        .limit(1)
    )
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
async def generate_daily_report(
    account_id: uuid.UUID = Depends(require_account_id),
) -> PipelineActionOut:
    """Gera o relatorio diario sob demanda (enfileira no Celery)."""
    try:
        from workers.pipeline_worker import generate_daily_report_task

        task = generate_daily_report_task.delay(account_id=str(account_id))
        return PipelineActionOut(ok=True, message="Relatorio diario enfileirado.", task_id=str(task.id))
    except Exception as e:  # noqa: BLE001
        log.error("api.daily_report_failed", error=str(e))
        return PipelineActionOut(ok=False, message=f"Falha ao enfileirar: {e}")


# -------------------------------- Hunt ----------------------------------
@router.get(
    "/hunt/settings",
    response_model=HuntSettingsOut,
    dependencies=[Depends(require_read_key)],
)
async def read_hunt_settings(
    account_id: uuid.UUID = Depends(require_account_id),
    session: AsyncSession = Depends(get_session),
) -> HuntSettingsOut:
    """Settings do cacador DESTA conta; cria o default desligado se nao existir."""
    settings_row = await hunt_service.get_settings(session, account_id)
    return HuntSettingsOut.model_validate(settings_row)


@router.put(
    "/hunt/settings",
    response_model=HuntSettingsOut,
    dependencies=[Depends(require_control_key)],
)
async def update_hunt_settings(
    payload: HuntSettingsIn,
    account_id: uuid.UUID = Depends(require_account_id),
    session: AsyncSession = Depends(get_session),
) -> HuntSettingsOut:
    """Liga/desliga o cacador, define frequencia (manual|daily|weekly|monthly)
    e o tema das buscas. frequency='manual' nunca roda sozinho."""
    settings_row = await hunt_service.save_settings(
        session,
        account_id,
        enabled=payload.enabled,
        frequency=payload.frequency.value,
        topic=payload.topic,
    )
    return HuntSettingsOut.model_validate(settings_row)


@router.post(
    "/hunt/run",
    response_model=HuntRunOut,
    dependencies=[Depends(require_control_key)],
)
async def run_hunt_now(
    account_id: uuid.UUID = Depends(require_account_id),
) -> HuntRunOut:
    """Roda a busca AGORA com o topic da conta (enfileira no Celery).

    O run_id retornado e o task id do Celery; o registro de uso (HuntRun)
    e gravado pelo worker ao iniciar a rodada.
    """
    try:
        from workers.pipeline_worker import run_hunt_task

        task = run_hunt_task.delay(account_id=str(account_id), trigger="manual")
        return HuntRunOut(status="queued", run_id=str(task.id), message="Busca enfileirada.")
    except Exception as e:  # noqa: BLE001
        log.error("api.hunt_run_failed", error=str(e))
        return HuntRunOut(status="error", message=f"Falha ao enfileirar: {e}")


# ------------------------------ Pipeline --------------------------------
@router.post(
    "/pipeline/start",
    response_model=PipelineActionOut,
    dependencies=[Depends(require_control_key)],
)
async def start_pipeline(
    account_id: uuid.UUID = Depends(require_account_id),
) -> PipelineActionOut:
    """Liga o modo continuo DESTA conta e ja inicia a primeira rodada.

    A partir daqui cada rodada se auto-encadeia (workers.pipeline_worker.
    scheduled_run) ate o Stop. Nao esperamos o Beat para comecar.
    """
    ok = pipeline_control.set_enabled(str(account_id), True)
    if not ok:
        return PipelineActionOut(ok=False, message="Falha ao habilitar (Redis indisponivel).")

    # Dispara a primeira rodada imediatamente; as proximas se auto-encadeiam.
    try:
        from workers.pipeline_worker import scheduled_run

        task = scheduled_run.delay(account_id=str(account_id))
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
async def stop_pipeline(
    account_id: uuid.UUID = Depends(require_account_id),
) -> PipelineActionOut:
    ok = pipeline_control.set_enabled(str(account_id), False)
    msg = "Pipeline desabilitada." if ok else "Falha ao desabilitar (Redis indisponivel)."
    return PipelineActionOut(ok=ok, message=msg)


@router.get(
    "/pipeline/status",
    response_model=PipelineStatusOut,
    dependencies=[Depends(require_read_key)],
)
async def pipeline_status(
    account_id: uuid.UUID = Depends(require_account_id),
) -> PipelineStatusOut:
    acc = str(account_id)
    return PipelineStatusOut(
        enabled=pipeline_control.is_enabled(acc),
        redis_available=pipeline_control.redis_available(),
        last_run=pipeline_control.get_status(acc) or None,
    )


@router.post(
    "/pipeline/run-once",
    response_model=PipelineActionOut,
    dependencies=[Depends(require_control_key)],
)
async def run_pipeline_once(
    account_id: uuid.UUID = Depends(require_account_id),
) -> PipelineActionOut:
    """Enfileira uma rodada unica no Celery e retorna o id da tarefa.

    Requer o worker Celery rodando. Se o broker estiver fora, retorna erro claro.
    """
    try:
        from workers.pipeline_worker import run_pipeline_once_task

        task = run_pipeline_once_task.delay(account_id=str(account_id))
        return PipelineActionOut(ok=True, message="Rodada enfileirada.", task_id=str(task.id))
    except Exception as e:  # noqa: BLE001
        log.error("api.run_once_failed", error=str(e))
        return PipelineActionOut(ok=False, message=f"Falha ao enfileirar: {e}")
