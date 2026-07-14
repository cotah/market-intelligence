"""Agente 11 - Daily Report.

Diferente dos outros: nao processa um topico, e sim consolida TODAS as
oportunidades de um dia em um relatorio executivo e salva em daily_reports.

Promissoras: score_total >= MIN_SCORE_TO_KEEP.
Excelentes:  score_total >= MIN_SCORE_FOR_PROJECT_PLAN.
"""

import json
import traceback
import uuid
from datetime import date, datetime, time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core import llm
from core.config import settings
from core.logging_config import get_logger
from models import DailyReport, Opportunity, OpportunityStatus

log = get_logger("agents.daily_report")

_SYSTEM = (
    "You are a chief of staff writing a crisp daily executive briefing about "
    "business opportunities discovered today. Be concise and decision-oriented."
)


class DailyReportAgent:
    name = "daily_report"

    async def generate(
        self,
        session: AsyncSession,
        account_id: uuid.UUID,
        report_date: date | None = None,
    ) -> DailyReport:
        day = report_date or date.today()
        start = datetime.combine(day, time.min)
        end = datetime.combine(day, time.max)
        log.info("daily_report.started", date=day.isoformat(), account_id=str(account_id))

        stmt = select(Opportunity).where(
            Opportunity.account_id == account_id,
            Opportunity.created_at >= start,
            Opportunity.created_at <= end,
        )
        result = await session.execute(stmt)
        opps = list(result.scalars().all())

        total_analyzed = len(opps)
        kept = [o for o in opps if o.score_total is not None]
        # `kept` so tem score_total nao-nulo; o "or 0.0" e apenas para o mypy.
        promising = [o for o in kept if (o.score_total or 0.0) >= settings.min_score_to_keep]
        excellent = [
            o for o in kept if (o.score_total or 0.0) >= settings.min_score_for_project_plan
        ]
        best = max(kept, key=lambda o: o.score_total or 0.0, default=None)

        summary_text = await self._llm_summary(day, total_analyzed, promising, excellent, best)

        payload = {
            "best_of_day": (
                {"id": str(best.id), "title": best.title, "score": best.score_total}
                if best
                else None
            ),
            "promising": [
                {"id": str(o.id), "title": o.title, "score": o.score_total} for o in promising
            ],
            "discarded": sum(1 for o in opps if o.status == OpportunityStatus.DISCARDED),
        }

        report = DailyReport(
            account_id=account_id,
            report_date=day,
            total_analyzed=total_analyzed,
            promising_count=len(promising),
            excellent_count=len(excellent),
            summary=summary_text,
            payload=payload,
        )
        session.add(report)
        await session.flush()
        log.info(
            "daily_report.completed",
            date=day.isoformat(),
            total=total_analyzed,
            promising=len(promising),
            excellent=len(excellent),
        )
        return report

    async def _llm_summary(self, day, total, promising, excellent, best) -> str:
        best_block = (
            f"{best.title} (score {best.score_total})" if best else "none scored today"
        )
        promising_titles = [o.title for o in promising[:10]]

        prompt = f"""Date: {day.isoformat()}
Total opportunities analyzed: {total}
Promising (kept): {len(promising)}
Excellent (score >= {settings.min_score_for_project_plan}): {len(excellent)}
Best of the day: {best_block}
Promising titles: {json.dumps(promising_titles, ensure_ascii=False)}

Write a 4-6 sentence executive summary of today's findings for the founder.
Plain text, no JSON."""

        try:
            return await llm.ask(prompt, system=_SYSTEM, max_tokens=600, temperature=0.4)
        except Exception as e:  # noqa: BLE001 - relatorio nao deve quebrar por falha de LLM
            log.warning("daily_report.summary_failed", error=str(e), traceback=traceback.format_exc())
            return (
                f"{total} oportunidades analisadas em {day.isoformat()}. "
                f"{len(promising)} promissoras, {len(excellent)} excelentes. "
                f"Melhor do dia: {best_block}. (Resumo automatico: LLM indisponivel.)"
            )
