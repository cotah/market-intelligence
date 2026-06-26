"""Orquestrador da pipeline de agentes.

FASE 1: liga Trend Hunter (descoberta de topicos) -> Problem Hunter.
Cada topico vira uma Opportunity no banco. Se um agente sinaliza descarte,
gravamos o motivo e marcamos status=DISCARDED antes de parar.

Os agentes 3-11 serao adicionados a `self.agents` na Fase 2, sem mudar
a estrutura de orquestracao.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from agents.ai_opportunity import AIOpportunityAgent
from agents.base import BaseAgent, PipelineContext
from agents.competitor_hunter import CompetitorHunterAgent
from agents.devils_advocate import DevilsAdvocateAgent
from agents.founder_compatibility import FounderCompatibilityAgent
from agents.market_size import MarketSizeAgent
from agents.monetization import MonetizationAgent
from agents.problem_hunter import ProblemHunterAgent
from agents.project_generator import ProjectGeneratorAgent
from agents.scorer import ScorerAgent
from agents.trend_hunter import TrendHunterAgent
from core.config import settings
from core.founder_profile_service import get_profile, profile_to_dict
from core.logging_config import get_logger
from models import Opportunity, OpportunityStatus

log = get_logger("pipeline")

# Mapeia o nome do agente -> campo JSONB correspondente na Opportunity.
_AGENT_FIELD_MAP: dict[str, str] = {
    "problem_hunter": "problem_data",
    "competitor_hunter": "competitor_data",
    "market_size": "market_data",
    "ai_opportunity": "ai_opportunity_data",
    "founder_compatibility": "compatibility_data",
    "monetization": "monetization_data",
    "scorer": "score_data",
    "devils_advocate": "devils_advocate_data",
    "project_generator": "project_plan",
}


class Pipeline:
    def __init__(self) -> None:
        self.trend_hunter = TrendHunterAgent()
        # Sequencia de agentes que processam cada topico (apos o Trend Hunter),
        # na ordem do README. Os criterios de descarte ficam dentro de cada agente.
        self.agents: list[BaseAgent] = [
            ProblemHunterAgent(),          # descarta se nao ha dor real
            CompetitorHunterAgent(),
            MarketSizeAgent(),
            AIOpportunityAgent(),
            FounderCompatibilityAgent(),   # descarta se compatibilidade < 50%
            MonetizationAgent(),
            ScorerAgent(),                 # descarta se score < MIN_SCORE_TO_KEEP; seta score_total
            DevilsAdvocateAgent(),
            ProjectGeneratorAgent(),       # so gera plano se score >= MIN_SCORE_FOR_PROJECT_PLAN
        ]

    async def run_once(self, session: AsyncSession, topics_limit: int | None = None) -> dict:
        """Roda uma rodada completa: descobre topicos e processa cada um.

        Retorna um resumo {topics, completed, discarded, opportunity_ids}.
        """
        limit = topics_limit or settings.pipeline_topics_per_run
        log.info("pipeline.run_once.started", topics_limit=limit)

        # Carrega o perfil do fundador uma vez por rodada (compartilhado entre topicos).
        profile = profile_to_dict(await get_profile(session))

        discovery = await self.trend_hunter.discover_topics(limit=limit)
        topics = discovery.get("topics", [])

        # Log explicito de quantos (e quais) topicos o Trend Hunter achou.
        topic_names = [t.get("name", "?") for t in topics]
        log.info("pipeline.topics_discovered", count=len(topics), topics=topic_names)
        if not topics:
            log.warning(
                "pipeline.no_topics_found",
                hint="Trend Hunter retornou 0 topicos. Verifique Serper/Grok/Perplexity/LLM.",
            )

        # `discards` guarda o motivo de cada descarte (topico + agente + razao),
        # tanto para os logs quanto para aparecer no status/dashboard.
        summary = {
            "topics": len(topics),
            "completed": 0,
            "discarded": 0,
            "discards": [],
            "opportunity_ids": [],
        }

        for index, topic_data in enumerate(topics, start=1):
            log.info(
                "pipeline.topic.processing",
                position=f"{index}/{len(topics)}",
                topic=topic_data.get("name", "?"),
            )
            opp = await self._process_topic(session, topic_data, profile)
            summary["opportunity_ids"].append(str(opp.id))
            if opp.status == OpportunityStatus.DISCARDED:
                summary["discarded"] += 1
                summary["discards"].append(
                    {"topic": opp.title, "by": opp.discarded_by, "reason": opp.discard_reason}
                )
            else:
                summary["completed"] += 1

        # Resumo final legivel: quantos entraram, quantos passaram, quantos
        # caíram e o porque de cada queda.
        log.info(
            "pipeline.run_once.completed",
            topics=summary["topics"],
            completed=summary["completed"],
            discarded=summary["discarded"],
            discards=summary["discards"],
        )
        return summary

    async def _process_topic(
        self, session: AsyncSession, topic_data: dict, profile: dict | None = None
    ) -> Opportunity:
        topic_name = topic_data.get("name", "Unknown topic")

        opp = Opportunity(
            title=topic_name,
            topic_origin=topic_name,
            source="trend_hunter",
            status=OpportunityStatus.IN_PROGRESS,
            trend_data=topic_data,
        )
        session.add(opp)
        await session.flush()  # garante opp.id

        log.info("pipeline.topic.started", topic=topic_name, opportunity_id=str(opp.id))

        context = PipelineContext(
            topic=topic_name,
            opportunity_id=str(opp.id),
            trend_data=topic_data,
            founder_profile=profile,
        )

        for agent in self.agents:
            result = await agent.run(context)

            # Persiste o dado do agente no campo correspondente.
            field = _AGENT_FIELD_MAP.get(agent.name)
            if field and result.data:
                setattr(opp, field, result.data)
                setattr(context, field, result.data)

            # Atualiza score_total se o scorer rodou.
            if agent.name == "scorer" and result.data:
                opp.score_total = result.data.get("total")

            if result.should_discard:
                opp.status = OpportunityStatus.DISCARDED
                opp.discard_reason = result.discard_reason
                opp.discarded_by = agent.name
                log.info(
                    "pipeline.topic.discarded",
                    topic=topic_name,
                    by=agent.name,
                    reason=result.discard_reason,
                )
                await session.flush()
                return opp

            # Rastreia cada agente que o topico passou, para saber exatamente
            # ate onde ele chegou antes de (eventualmente) ser descartado.
            log.info("pipeline.agent.passed", topic=topic_name, agent=agent.name)

        opp.status = OpportunityStatus.COMPLETED
        await session.flush()
        log.info(
            "pipeline.topic.completed",
            topic=topic_name,
            opportunity_id=str(opp.id),
            score_total=opp.score_total,
        )
        return opp


pipeline = Pipeline()
