"""Modelo de relatorio diario consolidado (Agente 11)."""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class DailyReport(Base):
    __tablename__ = "daily_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    report_date: Mapped[date] = mapped_column(Date, index=True)

    total_analyzed: Mapped[int] = mapped_column(Integer, default=0)
    promising_count: Mapped[int] = mapped_column(Integer, default=0)
    excellent_count: Mapped[int] = mapped_column(Integer, default=0)

    summary: Mapped[str] = mapped_column(Text, default="")
    # Detalhe completo: melhor do dia, lista de oportunidades, etc.
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    def __repr__(self) -> str:
        return f"<DailyReport {self.report_date} analyzed={self.total_analyzed}>"
