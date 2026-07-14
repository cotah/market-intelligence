"""Modelo de relatorio diario consolidado (Agente 11)."""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, Index, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base

# Mantido em sync com core.tenancy.OWNER_ACCOUNT_ID (backfill pre-multi-tenant).
_OWNER_ACCOUNT_DEFAULT = text("'00000000-0000-0000-0000-000000000001'")


class DailyReport(Base):
    __tablename__ = "daily_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Multi-tenancy: conta dona deste relatorio (1 relatorio/dia POR conta).
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, server_default=_OWNER_ACCOUNT_DEFAULT
    )

    report_date: Mapped[date] = mapped_column(Date, index=True)

    total_analyzed: Mapped[int] = mapped_column(Integer, default=0)
    promising_count: Mapped[int] = mapped_column(Integer, default=0)
    excellent_count: Mapped[int] = mapped_column(Integer, default=0)

    summary: Mapped[str] = mapped_column(Text, default="")
    # Detalhe completo: melhor do dia, lista de oportunidades, etc.
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        Index("ix_daily_reports_account_date", "account_id", "report_date"),
    )

    def __repr__(self) -> str:
        return f"<DailyReport {self.report_date} analyzed={self.total_analyzed}>"
