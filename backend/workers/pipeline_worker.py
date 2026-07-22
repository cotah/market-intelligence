"""Tarefas Celery que executam a pipeline e o relatorio diario.

Como a pipeline e async e cada tarefa Celery roda de forma sincrona, criamos
um engine novo dentro de cada execucao e usamos asyncio.run().

Sessoes curtas: as tasks da pipeline passam uma FABRICA de sessoes
(`_with_session_factory`) — a pipeline abre sessoes curtas so para ler/gravar
e NUNCA segura conexao durante as LLMs. O engine usa NullPool: fechar a
sessao FECHA a conexao de verdade (pool normal a devolveria ao pool, mas ela
continuaria aberta no servidor). Operacoes one-shot (hunt start/finish,
dispatcher, relatorio diario) continuam com `_with_session`.

Multi-tenancy: toda task carrega o account_id da conta dona da rodada —
as Opportunities/relatorios criados sao carimbados com ele. O Beat dispara
`scheduled_run` sem conta (modo dispatcher): ela varre as contas com a
pipeline habilitada e enfileira uma rodada por conta.
"""

import asyncio
import traceback
import uuid

import sentry_sdk
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, time
from typing import TypeVar

from sqlalchemy import distinct, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from agents.daily_report import DailyReportAgent
from celery_app import celery
from core import hunt_service, pipeline_control
from core.config import settings
from core.logging_config import get_logger
from core.pipeline import pipeline
from models import HuntRun, HuntSettings, Opportunity

log = get_logger("workers.pipeline")

T = TypeVar("T")


def _make_engine() -> AsyncEngine:
    """Engine descartavel por task: NullPool + connect timeout curto.

    - NullPool: fechar a sessao FECHA a conexao no servidor (pool normal a
      manteria aberta ate o dispose — exatamente o que queremos evitar).
    - connect timeout curto (default do asyncpg e 60s): cada sessao abre uma
      conexao NOVA, entao um soluco do Postgres/rede interna nao pode pendurar
      o worker por um minuto — falha rapido e quem chamou decide o que fazer.
    """
    return create_async_engine(
        settings.database_url,
        poolclass=NullPool,
        connect_args={"timeout": 5},
    )


async def _with_session_factory(
    fn: Callable[[async_sessionmaker[AsyncSession]], Awaitable[T]],
) -> T:
    """Roda `fn(session_factory)` — quem recebe abre/fecha sessoes curtas.

    Usado pelas rodadas da pipeline: a fabrica permite que a pipeline nunca
    segure conexao durante as LLMs (cada commit e responsabilidade dela).
    """
    engine = _make_engine()
    try:
        return await fn(async_sessionmaker(engine, expire_on_commit=False))
    finally:
        await engine.dispose()


async def _with_session(fn: Callable[[AsyncSession], Awaitable[T]]) -> T:
    """Roda `fn(session)` com engine/sessao proprios e commit ao final.

    Para operacoes one-shot e rapidas (hunt start/finish, dispatcher,
    relatorio diario) — a sessao dura o tempo da operacao inteira.
    """
    engine = _make_engine()
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
        summary = asyncio.run(_with_session_factory(lambda sf: pipeline.run_once(sf, acc)))
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

        async def _run(session_factory):
            opp = await pipeline.run_for_idea(session_factory, acc, idea)
            return {
                "opportunity_id": str(opp.id),
                "title": opp.title,
                "status": opp.status.value,
                "score_total": opp.score_total,
            }

        summary = asyncio.run(_with_session_factory(_run))
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
        summary = asyncio.run(_with_session_factory(lambda sf: pipeline.run_once(sf, acc)))
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


# --------------------------------- Hunt ----------------------------------
@celery.task(name="workers.pipeline_worker.run_hunt_task", bind=True)
def run_hunt_task(self, account_id: str, trigger: str = "manual") -> dict | None:
    """Rodada do cacador DESTA conta, com o tema configurado em hunt_settings.

    - trigger="manual": disparada pelo POST /hunt/run.
    - trigger="scheduled": disparada pelo dispatcher do Beat (frequency).

    O uso e registrado em hunt_runs (base do debito de Caps na Fase 2) e o
    last_run_at/next_run_at da conta sao atualizados ao final — mesmo em falha,
    para a frequencia nao re-disparar em loop uma rodada quebrada.
    """
    log.info(
        "worker.hunt.received", task_id=self.request.id, account_id=account_id, trigger=trigger
    )
    acc = uuid.UUID(account_id)

    # Mesma trava por conta do modo continuo: nunca duas rodadas simultaneas.
    if not pipeline_control.acquire_run_lock(account_id):
        log.info("worker.hunt.skipped", reason="already_running", account_id=account_id)
        return None

    run_pk: uuid.UUID | None = None
    try:
        # 1. Carrega settings e registra o INICIO do uso (sessao propria: o
        # registro sobrevive mesmo se a pipeline falhar depois).
        async def _start(session: AsyncSession) -> tuple[uuid.UUID, str]:
            settings_row = await hunt_service.get_settings(session, acc)
            run = await hunt_service.start_run(
                session,
                acc,
                run_id=self.request.id or "",
                topic=settings_row.topic,
                trigger=trigger,
            )
            return run.id, settings_row.topic

        run_pk, topic = asyncio.run(_with_session(_start))

        # 2. Roda a pipeline escopada no tema da conta.
        summary = asyncio.run(
            _with_session_factory(lambda sf: pipeline.run_once(sf, acc, niche=topic, source="hunt"))
        )

        # 3. Fecha o registro de uso e reagenda (last_run_at/next_run_at).
        asyncio.run(_with_session(lambda s: _finish_hunt_run(s, run_pk, success=True)))
        pipeline_control.set_status(
            account_id,
            {"trigger": f"hunt_{trigger}", "task_id": self.request.id, "topic": topic, **summary},
        )
        log.info(
            "worker.hunt.completed",
            account_id=account_id,
            topic=topic,
            **{k: v for k, v in summary.items() if k != "opportunity_ids"},
        )
        return summary
    except Exception as e:  # noqa: BLE001
        log.error(
            "worker.hunt.failed",
            account_id=account_id,
            error=str(e),
            error_type=type(e).__name__,
            traceback=traceback.format_exc(),
        )
        if run_pk is not None:
            try:
                asyncio.run(_with_session(lambda s: _finish_hunt_run(s, run_pk, success=False)))
            except Exception:  # noqa: BLE001
                log.error("worker.hunt.finish_record_failed", account_id=account_id)
        raise
    finally:
        pipeline_control.release_run_lock(account_id)


async def _finish_hunt_run(session: AsyncSession, run_pk: uuid.UUID, *, success: bool) -> None:
    run = await session.get(HuntRun, run_pk)
    if run is not None:
        await hunt_service.finish_run(session, run, success=success)


@celery.task(name="workers.pipeline_worker.hunt_scheduler_dispatch")
def hunt_scheduler_dispatch() -> dict:
    """Dispatcher do Beat: varre as contas com o cacador ligado e na hora.

    Barato (um SELECT indexado, sem LLM). frequency='manual' nunca entra
    aqui: manual nao tem next_run_at.
    """

    async def _due_accounts(session: AsyncSession) -> list[str]:
        stmt = select(HuntSettings.account_id).where(
            HuntSettings.enabled.is_(True),
            HuntSettings.next_run_at.is_not(None),
            HuntSettings.next_run_at <= datetime.now(UTC),
        )
        result = await session.execute(stmt)
        return [str(acc) for acc in result.scalars().all()]

    try:
        accounts = asyncio.run(_with_session(_due_accounts))
    except Exception as e:  # noqa: BLE001
        # Soluco do banco (ex: TimeoutError no connect) NAO derruba o tick:
        # loga, reporta ao Sentry como handled e devolve 0 contas — o Beat
        # re-tenta naturalmente no proximo tick (5 min).
        sentry_sdk.capture_exception(e)
        log.error(
            "worker.hunt_dispatch.failed",
            error=str(e),
            error_type=type(e).__name__,
            traceback=traceback.format_exc(),
        )
        return {"dispatched_accounts": 0, "error": type(e).__name__}
    for account_id in accounts:
        run_hunt_task.delay(account_id=account_id, trigger="scheduled")
    log.info("worker.hunt_dispatch.completed", accounts=len(accounts))
    return {"dispatched_accounts": len(accounts)}


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
