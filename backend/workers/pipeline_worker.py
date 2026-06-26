"""Tarefas Celery que executam a pipeline e o relatorio diario.

Como a pipeline e async e cada tarefa Celery roda de forma sincrona, criamos
um engine/sessao novos dentro de cada execucao e usamos asyncio.run().
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agents.daily_report import DailyReportAgent
from celery_app import celery
from core import pipeline_control
from core.config import settings
from core.logging_config import get_logger
from core.pipeline import pipeline

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
        return result
    finally:
        await engine.dispose()


# ------------------------------- Pipeline --------------------------------
@celery.task(name="workers.pipeline_worker.run_pipeline_once_task", bind=True)
def run_pipeline_once_task(self) -> dict:
    """Executa uma unica rodada da pipeline agora."""
    log.info("worker.run_once.started", task_id=self.request.id)
    try:
        summary = asyncio.run(_with_session(pipeline.run_once))
        pipeline_control.set_status({"last_task_id": self.request.id, **summary})
        log.info("worker.run_once.completed", **{k: v for k, v in summary.items() if k != "opportunity_ids"})
        return summary
    except Exception as e:  # noqa: BLE001
        log.error("worker.run_once.failed", error=str(e))
        raise


@celery.task(name="workers.pipeline_worker.scheduled_run", bind=True)
def scheduled_run(self) -> dict | None:
    """Rodada do modo continuo.

    Disparada pelo Start (1a rodada), pelo watchdog do Beat e pelo
    auto-encadeamento (cada rodada enfileira a proxima). So roda se a pipeline
    estiver habilitada e usa uma trava no Redis para nunca rodar duas rodadas
    ao mesmo tempo. Ao terminar, se ainda habilitada, ja enfileira a proxima
    rodada — e assim a pipeline roda continuamente ate o Stop.
    """
    if not pipeline_control.is_enabled():
        log.info("worker.scheduled.skipped", reason="pipeline_disabled")
        return None

    # Evita rodadas sobrepostas (auto-encadeamento + watchdog do Beat).
    if not pipeline_control.acquire_run_lock():
        log.info("worker.scheduled.skipped", reason="already_running")
        return None

    try:
        log.info("worker.scheduled.running", task_id=self.request.id)
        summary = asyncio.run(_with_session(pipeline.run_once))
        pipeline_control.set_status({"trigger": "scheduled", "task_id": self.request.id, **summary})
        log.info(
            "worker.scheduled.completed",
            **{k: v for k, v in summary.items() if k != "opportunity_ids"},
        )
        return summary
    finally:
        pipeline_control.release_run_lock()
        # Modo continuo: se ainda habilitada, ja agenda a proxima rodada.
        if pipeline_control.is_enabled():
            gap = settings.pipeline_continuous_gap_seconds
            scheduled_run.apply_async(countdown=gap)
            log.info("worker.scheduled.rechained", gap_seconds=gap)
        else:
            log.info("worker.scheduled.stopped", reason="pipeline_disabled")


# ----------------------------- Daily Report ------------------------------
async def _generate_daily_report(session: AsyncSession) -> dict:
    report = await DailyReportAgent().generate(session)
    return {
        "report_id": str(report.id),
        "date": report.report_date.isoformat(),
        "total_analyzed": report.total_analyzed,
        "promising_count": report.promising_count,
        "excellent_count": report.excellent_count,
    }


@celery.task(name="workers.pipeline_worker.generate_daily_report_task")
def generate_daily_report_task() -> dict:
    """Gera o relatorio diario consolidado (1x/dia via beat, ou sob demanda)."""
    log.info("worker.daily_report.started")
    summary = asyncio.run(_with_session(_generate_daily_report))
    log.info("worker.daily_report.completed", **summary)
    return summary
