"""Configuracao e historico do cacador de oportunidades (por conta).

HuntSettings: 1 linha POR conta (PK = account_id, mesmo padrao do
founder_profile). O cliente liga/desliga, escolhe a frequencia e o tema;
o Beat varre as contas habilitadas e roda na cadencia escolhida.
frequency='manual' NUNCA roda sozinho — so via POST /hunt/run.

HuntRun: registro de uso de cada rodada (base para o debito de Caps na
Fase 2 — por ora so registramos, sem cobrar).
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class HuntFrequency(str, enum.Enum):
    MANUAL = "manual"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class HuntSettings(Base):
    __tablename__ = "hunt_settings"

    # PK = conta dona das settings (1 linha por conta).
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)

    # Opt-in: default DESLIGADO para nao gastar credito sem o cliente querer.
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    frequency: Mapped[str] = mapped_column(
        String(20), nullable=False, default=HuntFrequency.MANUAL.value
    )
    # Tema/nicho das buscas (ex: "manicure em Dublin"). Vazio = busca aberta.
    topic: Mapped[str] = mapped_column(Text, nullable=False, default="")

    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Proxima rodada agendada; NULL quando manual ou desligado.
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<HuntSettings account={self.account_id} enabled={self.enabled} "
            f"frequency={self.frequency!r} topic={self.topic!r}>"
        )


class HuntRunStatus(str, enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class HuntRun(Base):
    __tablename__ = "hunt_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # Task id do Celery (o run_id devolvido pelo POST /hunt/run).
    run_id: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    topic: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # "manual" (POST /hunt/run) ou "scheduled" (Beat).
    trigger: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")

    status: Mapped[HuntRunStatus] = mapped_column(
        Enum(HuntRunStatus, name="hunt_run_status"),
        nullable=False,
        default=HuntRunStatus.RUNNING,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_hunt_runs_account_started", "account_id", "started_at"),
    )

    def __repr__(self) -> str:
        return f"<HuntRun account={self.account_id} trigger={self.trigger!r} status={self.status}>"
