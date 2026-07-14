"""Tarefas Celery que executam a pipeline e o relatorio diario.

Como a pipeline e async e cada tarefa Celery roda de forma sincrona, criamos
um engine/sessao novos dentro de cada execucao e usamos asyncio.run().

Multi-tenancy: toda task carrega o account_id da conta dona da rodada —
as Opportunities/relatorios criados sao carimbados com ele. O Beat dispara
`scheduled_run` sem conta (modo dispatcher): ela varre as contas com a
pipeline habilitada e enfileira uma rodada por conta.
"""

import asyncio
import traceback
import uuid
from collections.abc import Awaitable, Callable
from datetime import date, datetime, time
from typing import TypeVar

from sqlalchemy import distinct, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agents.daily_report import DailyReportAgent
from celery_app import celery
from core import pipeline_control
from core.config import settings
from core.logging_config import get_logger
from core.pipeline import pipeline
from models import Opportunity

log = get_logger("workers.pipeline")

T = TypeVar("T")


async def _with_session(fn: Callable[[AsyncSession], Awaitable[T]]) -> T:
    """Roda `fn(session)` com engine/sessao proprios e commit ao final."""
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            result = await fn(session)
            await session.commit()
            # Confirma que o commit ocorreu: se este log NAO aparecer mas os
            # logs dos agentes aparecerem, houve rollback (excecao antes daqui).
            log.info("worker.session.committed")
        return result
    finally:
        await engine.dispose()


# ------------------------------- Pipeline --------------------------------
@celery.task(name="workers.pipeline_worker.run_pipeline_once_task", bind=True)
def run_pipeline_once_task(self, account_id: str) -> dict:
    """Executa uma unica rodada da pipeline agora, para a conta informada."""
    # PRIMEIRO log, antes de qualquer await/asyncio.run: confirma que o worker
    # realmente PEGOU a task (e em qual fila chegou), nao so que foi enfileirada.
    delivery = getattr(self.request, "delivery_info", {}) or {}
    log.info(
        "worker.run_once.received",
        task_id=self.request.id,
        queue=delivery.get("routing_key"),
        account_id=account_id,
    )
    try:
        log.info("worker.run_once.started", task_id=self.request.id, account_id=account_id)
        acc = uuid.UUID(account_id)
        summary = asyncio.run(_with_session(lambda s: pipeline.run_once(s, acc)))
        pipeline_control.set_status(
            account_id, {"last_task_id": self.request.id, **summary}
        )
        log.info("worker.run_once.completed", **{k: v for k, v in summary.items() if k != "opportunity_ids"})
        return summary
    except Exception as e:  # noqa: BLE001
        # traceback explicito: garante que um erro silencioso fique visivel
        # mesmo com o JSONRenderer (que nao formata exc_info sozinho).
        log.error(
            "worker.run_once.failed",
            error=str(e),
            error_type=type(e).__name__,
            traceback=traceback.format_exc(),
        )
        raise


@celery.task(name="workers.pipeline_worker.run_for_idea_task", bind=True)
def run_for_idea_task(self, idea: dict, account_id: str) -> dict:
    """Modo Ideia: analisa um produto/ideia trazido pelo fundador.

    Roda a mesma cadeia de agentes, mas semeada com a ideia (sem Trend Hunter).
    """
    log.info("worker.run_for_idea.received", task_id=self.request.id, account_id=account_id)
    try:
        acc = uuid.UUID(account_id)

        async def _run(session):
            opp = await pipeline.run_for_idea(session, acc, idea)
            return {
                "opportunity_id": str(opp.id),
                "title": opp.title,
                "status": opp.status.value,
                "score_total": opp.score_total,
            }

        summary = asyncio.run(_with_session(_run))
        pipeline_control.set_status(
            account_id, {"trigger": "idea", "task_id": self.request.id, **summary}
        )
        log.info("worker.run_for_idea.completed", **summary)
        return summary
    except Exception as e:  # noqa: BLE001
        log.error(
            "worker.run_for_idea.failed",
            error=str(e),
            error_type=type(e).__name__,
            traceback=traceback.format_exc(),
        )
        raise


@celery.task(name="workers.pipeline_worker.scheduled_run", bind=True)
def scheduled_run(self, account_id: str | None = None) -> dict | None:
    """Rodada do modo continuo (por conta).

    Dois modos:
    - SEM account_id (Beat/watchdog): varre as contas habilitadas e enfileira
      uma rodada para cada uma (dispatcher — nao roda pipeline aqui).
    - COM account_id (Start da API ou auto-encadeamento): roda a rodada da
      conta, com trava por conta para nunca sobrepor duas rodadas dela.
      Ao terminar, se a conta ainda estiver habilitada, ja enfileira a
      proxima rodada — e assim a pipeline roda continuamente ate o Stop.
    """
    # PRIMEIRO log, antes de qualquer await: confirma que o worker pegou a task.
    delivery = getattr(self.request, "delivery_info", {}) or {}
    log.info(
        "worker.scheduled.received",
        task_id=self.request.id,
        queue=delivery.get("routing_key"),
        account_id=account_id,
    )

    # Modo dispatcher (Beat): uma task filha por conta habilitada.
    if account_id is None:
        accounts = pipeline_control.enabled_accounts()
        for enabled_account in accounts:
            scheduled_run.delay(account_id=enabled_account)
        log.info("worker.scheduled.dispatched", accounts=len(accounts))
        return {"dispatched_accounts": len(accounts)}

    if not pipeline_control.is_enabled(account_id):
        log.info("worker.scheduled.skipped", reason="pipeline_disabled", account_id=account_id)
        return None

    # Evita rodadas sobrepostas da MESMA conta (auto-encadeamento + watchdog).
    if not pipeline_control.acquire_run_lock(account_id):
        log.info("worker.scheduled.skipped", reason="already_running", account_id=account_id)
        return None

    try:
        log.info("worker.scheduled.running", task_id=self.request.id, account_id=account_id)
        acc = uuid.UUID(account_id)
        summary = asyncio.run(_with_session(lambda s: pipeline.run_once(s, acc)))
        pipeline_control.set_status(
            account_id, {"trigger": "scheduled", "task_id": self.request.id, **summary}
        )
        log.info(
            "worker.scheduled.completed",
            account_id=account_id,
            **{k: v for k, v in summary.items() if k != "opportunity_ids"},
        )
        return summary
    except Exception as e:  # noqa: BLE001
        # Erro silencioso vira visivel (com traceback), mesmo no JSONRenderer.
        log.error(
            "worker.scheduled.failed",
            error=str(e),
            error_type=type(e).__name__,
            traceback=traceback.format_exc(),
        )
        raise
    finally:
        pipeline_control.release_run_lock(account_id)
        # Modo continuo: se a conta ainda esta habilitada, agenda a proxima rodada.
        if pipeline_control.is_enabled(account_id):
            gap = settings.pipeline_continuous_gap_seconds
            scheduled_run.apply_async(kwargs={"account_id": account_id}, countdown=gap)
            log.info("worker.scheduled.rechained", gap_seconds=gap, account_id=account_id)
        else:
            log.info("worker.scheduled.stopped", reason="pipeline_disabled", account_id=account_id)


# ----------------------------- Daily Report ------------------------------
async def _generate_daily_report(session: AsyncSession, account_id: uuid.UUID) -> dict:
    report = await DailyReportAgent().generate(session, account_id)
    return {
        "report_id": str(report.id),
        "account_id": str(account_id),
        "date": report.report_date.isoformat(),
        "total_analyzed": report.total_analyzed,
        "promising_count": report.promising_count,
        "excellent_count": report.excellent_count,
    }


async def _accounts_with_activity_today(session: AsyncSession) -> list[uuid.UUID]:
    """Contas que criaram oportunidades hoje (para o relatorio diario do Beat)."""
    day = date.today()
    stmt = select(distinct(Opportunity.account_id)).where(
        Opportunity.created_at >= datetime.combine(day, time.min),
        Opportunity.created_at <= datetime.combine(day, time.max),
    )
    result = await session.execute(stmt)
    return [row for row in result.scalars().all()]


@celery.task(name="workers.pipeline_worker.generate_daily_report_task")
def generate_daily_report_task(account_id: str | None = None) -> dict | list[dict]:
    """Gera o relatorio diario consolidado.

    - COM account_id (sob demanda pela API): gera o relatorio DA conta.
    - SEM account_id (Beat, 1x/dia): gera um relatorio para CADA conta que
      teve oportunidades criadas hoje.
    """
    log.info("worker.daily_report.started", account_id=account_id)

    if account_id is not None:
        acc = uuid.UUID(account_id)
        summary = asyncio.run(_with_session(lambda s: _generate_daily_report(s, acc)))
        log.info("worker.daily_report.completed", **summary)
        return summary

    async def _run_for_all(session: AsyncSession) -> list[dict]:
        accounts = await _accounts_with_activity_today(session)
        return [await _generate_daily_report(session, acc) for acc in accounts]

    summaries = asyncio.run(_with_session(_run_for_all))
    log.info("worker.daily_report.completed_all", reports=len(summaries))
    return summaries
