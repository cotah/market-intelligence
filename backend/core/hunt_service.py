"""Regras do cacador de oportunidades controlado pelo cliente.

Get-or-create das settings (default DESLIGADO — opt-in), calculo do
next_run_at por frequencia e registro de uso (HuntRun) de cada rodada.
O debito de Caps por rodada entra na Fase 2 — por ora so registramos.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from core.logging_config import get_logger
from models import HuntFrequency, HuntRun, HuntRunStatus, HuntSettings

log = get_logger("hunt_service")

# Intervalo de cada frequencia automatica. "manual" nunca agenda.
_FREQUENCY_DELTAS: dict[str, timedelta] = {
    HuntFrequency.DAILY.value: timedelta(days=1),
    HuntFrequency.WEEKLY.value: timedelta(weeks=1),
    HuntFrequency.MONTHLY.value: timedelta(days=30),
}


def compute_next_run_at(
    enabled: bool, frequency: str, base: datetime | None = None
) -> datetime | None:
    """Proxima rodada agendada. None quando desligado ou manual."""
    delta = _FREQUENCY_DELTAS.get(frequency)
    if not enabled or delta is None:
        return None
    return (base or datetime.now(UTC)) + delta


async def get_settings(session: AsyncSession, account_id: uuid.UUID) -> HuntSettings:
    """Retorna as settings da conta, criando o default desligado se nao existir."""
    settings_row = await session.get(HuntSettings, account_id)
    if settings_row is None:
        # Defaults explicitos (nao so no INSERT): a linha ja nasce valida
        # em memoria, mesmo antes do flush.
        settings_row = HuntSettings(
            account_id=account_id,
            enabled=False,
            frequency=HuntFrequency.MANUAL.value,
            topic="",
        )
        session.add(settings_row)
        await session.flush()
        log.info("hunt_settings.seeded", account_id=str(account_id))
    return settings_row


async def save_settings(
    session: AsyncSession,
    account_id: uuid.UUID,
    *,
    enabled: bool,
    frequency: str,
    topic: str,
) -> HuntSettings:
    """Atualiza as settings da conta e recalcula o next_run_at."""
    settings_row = await get_settings(session, account_id)
    settings_row.enabled = enabled
    settings_row.frequency = frequency
    settings_row.topic = topic.strip()
    if not enabled or frequency not in _FREQUENCY_DELTAS:
        settings_row.next_run_at = None
    elif settings_row.last_run_at is None:
        # Primeira vez ligando: roda ja na proxima varredura do Beat.
        settings_row.next_run_at = datetime.now(UTC)
    else:
        settings_row.next_run_at = compute_next_run_at(
            enabled, frequency, base=settings_row.last_run_at
        )
    await session.flush()
    log.info(
        "hunt_settings.saved",
        account_id=str(account_id),
        enabled=enabled,
        frequency=frequency,
        topic=settings_row.topic,
        next_run_at=settings_row.next_run_at.isoformat() if settings_row.next_run_at else None,
    )
    return settings_row


def settings_to_dict(settings_row: HuntSettings) -> dict:
    return {
        "enabled": settings_row.enabled,
        "frequency": settings_row.frequency,
        "topic": settings_row.topic,
        "last_run_at": settings_row.last_run_at,
        "next_run_at": settings_row.next_run_at,
    }


async def start_run(
    session: AsyncSession,
    account_id: uuid.UUID,
    *,
    run_id: str,
    topic: str,
    trigger: str,
) -> HuntRun:
    """Registra o inicio de uma rodada (uso — base do debito de Caps na Fase 2)."""
    run = HuntRun(account_id=account_id, run_id=run_id, topic=topic, trigger=trigger)
    session.add(run)
    await session.flush()
    log.info(
        "hunt_run.started",
        account_id=str(account_id),
        run_id=run_id,
        topic=topic,
        trigger=trigger,
    )
    return run


async def finish_run(
    session: AsyncSession, run: HuntRun, *, success: bool
) -> None:
    """Fecha o registro da rodada e atualiza last_run_at/next_run_at da conta."""
    now = datetime.now(UTC)
    run.status = HuntRunStatus.COMPLETED if success else HuntRunStatus.FAILED
    run.finished_at = now

    settings_row = await get_settings(session, run.account_id)
    settings_row.last_run_at = now
    settings_row.next_run_at = compute_next_run_at(
        settings_row.enabled, settings_row.frequency, base=now
    )
    await session.flush()
    log.info(
        "hunt_run.finished",
        account_id=str(run.account_id),
        run_id=run.run_id,
        status=run.status.value,
        next_run_at=settings_row.next_run_at.isoformat() if settings_row.next_run_at else None,
    )
