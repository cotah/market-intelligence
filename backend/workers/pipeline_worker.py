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


@celery.task(name="workers.pipeline_worker.scheduled_run")
def scheduled_run() -> dict | None:
    """Disparada pelo beat. So roda se a pipeline estiver habilitada."""
    if not pipeline_control.is_enabled():
        log.info("worker.scheduled.skipped", reason="pipeline_disabled")
        return None
    log.info("worker.scheduled.running")
    summary = asyncio.run(_with_session(pipeline.run_once))
    pipeline_control.set_status({"trigger": "scheduled", **summary})
    return summary


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
