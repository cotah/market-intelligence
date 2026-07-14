"""Modelo de oportunidade.

Guarda o resultado de cada agente em colunas JSONB separadas, mais o
score total (indexado) e o status na pipeline. Cada descarte registra
o motivo em `discard_reason` para rastreabilidade total.
"""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Float, Index, String, Text, func, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base

# server_default do account_id: workspace do dono (backfill pre-multi-tenant).
# Mantido em sync com core.tenancy.OWNER_ACCOUNT_ID.
_OWNER_ACCOUNT_DEFAULT = text("'00000000-0000-0000-0000-000000000001'")


class OpportunityStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    # Terminou a cadeia, mas com pelo menos um agente falho (dado faltando).
    # Nunca deve se passar por COMPLETED — veja `failed_agents`.
    PARTIAL = "partial"
    DISCARDED = "discarded"


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # --- Multi-tenancy: conta dona desta oportunidade ---
    # O codigo SEMPRE carimba explicitamente; o server_default cobre apenas
    # o backfill de linhas antigas (workspace do dono).
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, server_default=_OWNER_ACCOUNT_DEFAULT
    )

    # --- Identificacao ---
    title: Mapped[str] = mapped_column(String(500), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    topic_origin: Mapped[str] = mapped_column(String(500), default="")
    source: Mapped[str] = mapped_column(String(100), default="trend_hunter")

    # --- Estado na pipeline ---
    status: Mapped[OpportunityStatus] = mapped_column(
        SAEnum(OpportunityStatus, name="opportunity_status"),
        default=OpportunityStatus.IN_PROGRESS,
    )
    discard_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    discarded_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Agentes que falharam durante a cadeia: [{"agent": nome, "error": msg}].
    # Preenchido mesmo em DISCARDED, para rastreabilidade total.
    failed_agents: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # --- Dados de cada agente (JSONB) ---
    trend_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    problem_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    competitor_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    market_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ai_opportunity_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    compatibility_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    monetization_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    score_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    project_plan: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    devils_advocate_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # --- Score total (extraido de score_data, indexado para filtros) ---
    score_total: Mapped[float | None] = mapped_column(Float, nullable=True)

    # --- Timestamps ---
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_opportunities_score_total", "score_total"),
        Index("ix_opportunities_created_at", "created_at"),
        Index("ix_opportunities_status", "status"),
        # Indices compostos: toda leitura da API filtra por account_id.
        Index("ix_opportunities_account_created", "account_id", "created_at"),
        Index("ix_opportunities_account_score", "account_id", "score_total"),
    )

    def __repr__(self) -> str:
        return f"<Opportunity {self.id} '{self.title}' score={self.score_total} status={self.status}>"
