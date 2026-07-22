"""Orquestrador da pipeline de agentes.

Cada topico vira uma Opportunity no banco. Se um agente sinaliza descarte,
gravamos o motivo e marcamos status=DISCARDED antes de parar.

Sessoes curtas: a pipeline recebe uma FABRICA de sessoes (nao uma sessao) e
abre sessoes curtas apenas para ler o perfil e para gravar cada Opportunity
pronta — NUNCA durante as chamadas de LLM, que levam minutos. A Opportunity
nasce e evolui em memoria; 1 commit por topico, ja com o status final.
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

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


def _compute_risk_flag(da_data: dict) -> str | None:
    """Regra deterministica da Opcao A: 2+ fatal flaws OU 3+ riscos "high".

    Retorna "high" quando o selo "Aprovado com ressalvas" deve ser aplicado,
    None caso contrario. Thresholds ajustaveis via Settings.
    """
    fatal_flaws = da_data.get("fatal_flaws") or []
    risks = da_data.get("risks") or []
    high_risks = sum(
        1
        for r in risks
        if isinstance(r, dict) and str(r.get("severity", "")).lower() == "high"
    )
    if (
        len(fatal_flaws) >= settings.risk_flag_min_fatal_flaws
        or high_risks >= settings.risk_flag_min_high_risks
    ):
        return "high"
    return None


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

    async def run_once(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        account_id: uuid.UUID,
        topics_limit: int | None = None,
        *,
        niche: str = "",
        source: str = "trend_hunter",
    ) -> dict:
        """Roda uma rodada completa PARA UMA CONTA: descobre topicos e processa cada um.

        Com `niche` (tema do cacador da conta), a descoberta fica escopada
        naquele tema. Retorna um resumo {topics, completed, discarded, opportunity_ids}.
        """
        limit = topics_limit or settings.pipeline_topics_per_run
        log.info(
            "pipeline.run_once.started",
            topics_limit=limit,
            account_id=str(account_id),
            niche=niche or None,
        )

        # Fase de leitura (sessao curta): carrega o perfil do fundador DA CONTA
        # uma vez por rodada. get_profile SEMEIA o perfil na primeira leitura,
        # entao o commit e necessario aqui.
        async with session_factory() as session:
            profile = profile_to_dict(await get_profile(session, account_id))
            await session.commit()

        discovery = await self.trend_hunter.discover_topics(limit=limit, niche=niche)
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
        summary: dict[str, Any] = {
            "topics": len(topics),
            "completed": 0,
            "partial": 0,
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
            opp = await self._process_topic(
                session_factory, account_id, topic_data, profile, source=source
            )
            summary["opportunity_ids"].append(str(opp.id))
            if opp.status == OpportunityStatus.DISCARDED:
                summary["discarded"] += 1
                summary["discards"].append(
                    {"topic": opp.title, "by": opp.discarded_by, "reason": opp.discard_reason}
                )
            elif opp.status == OpportunityStatus.PARTIAL:
                # PARTIAL nunca se esconde dentro de "completed".
                summary["partial"] += 1
            else:
                summary["completed"] += 1

        # Resumo final legivel: quantos entraram, quantos passaram, quantos
        # caíram e o porque de cada queda.
        log.info(
            "pipeline.run_once.completed",
            topics=summary["topics"],
            completed=summary["completed"],
            partial=summary["partial"],
            discarded=summary["discarded"],
            discards=summary["discards"],
        )
        return summary

    async def _process_topic(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        account_id: uuid.UUID,
        topic_data: dict,
        profile: dict | None = None,
        *,
        source: str = "trend_hunter",
        ignore_discard_from: set[str] | None = None,
    ) -> Opportunity:
        topic_name = topic_data.get("name", "Unknown topic")

        # Fase LLM: a Opportunity vive SO EM MEMORIA enquanto os agentes rodam
        # (minutos de LLM) — nenhuma sessao/conexao aberta. O id e gerado no
        # cliente para os logs; o banco so ve a linha no commit final.
        opp = Opportunity(
            id=uuid.uuid4(),
            account_id=account_id,
            title=topic_name,
            topic_origin=topic_name,
            source=source,
            status=OpportunityStatus.IN_PROGRESS,
            trend_data=topic_data,
        )

        log.info("pipeline.topic.started", topic=topic_name, opportunity_id=str(opp.id))

        context = PipelineContext(
            topic=topic_name,
            opportunity_id=str(opp.id),
            trend_data=topic_data,
            founder_profile=profile,
        )

        # Agentes que falharam (success=False): a cadeia continua (graceful
        # degradation), mas a falha fica registrada e o status final vira
        # PARTIAL — nunca um COMPLETED com dado faltando em silencio.
        failed_agents: list[dict] = []
        discarded = False

        for agent in self.agents:
            log.info("pipeline.agent.running", topic=topic_name, agent=agent.name)
            result = await agent.run(context)

            # Resultado de CADA agente: passou, descartou ou falhou, e se trouxe
            # dado. E aqui que se ve onde o topico parou de progredir.
            log.info(
                "pipeline.agent.result",
                topic=topic_name,
                agent=agent.name,
                success=result.success,
                should_discard=result.should_discard,
                has_data=bool(result.data),
                error=result.error or None,
            )

            # Persiste o dado do agente no campo correspondente.
            field = _AGENT_FIELD_MAP.get(agent.name)
            if field and result.data:
                setattr(opp, field, result.data)
                setattr(context, field, result.data)

            # Atualiza score_total se o scorer rodou.
            if agent.name == "scorer" and result.data:
                opp.score_total = result.data.get("total")

            # Opcao A (docs/PROPOSTA_SCORER_DEVILS_ADVOCATE.md): se o Devil's
            # Advocate encontra riscos demais, a aprovacao ganha o selo
            # "com ressalvas" em score_data.risk_flag — a nota nunca muda.
            if agent.name == "devils_advocate" and result.data and opp.score_data:
                flag = _compute_risk_flag(result.data)
                if flag:
                    # Dict novo (nao mutacao) para o JSONB ser marcado como dirty.
                    opp.score_data = {**opp.score_data, "risk_flag": flag}
                    context.score_data = opp.score_data
                    log.info(
                        "pipeline.risk_flag.applied",
                        topic=topic_name,
                        flag=flag,
                        fatal_flaws=len(result.data.get("fatal_flaws") or []),
                    )

            if not result.success:
                failed_agents.append({"agent": agent.name, "error": result.error})
                log.warning(
                    "pipeline.agent.failed_partial",
                    topic=topic_name,
                    agent=agent.name,
                    error=result.error,
                )

            if result.should_discard:
                if ignore_discard_from and agent.name in ignore_discard_from:
                    # Modo Ideia: este agente e informativo — registra o dado e
                    # loga, mas NAO descarta (a cadeia continua).
                    log.info(
                        "pipeline.discard_ignored",
                        topic=topic_name,
                        agent=agent.name,
                        reason=result.discard_reason,
                    )
                else:
                    opp.status = OpportunityStatus.DISCARDED
                    opp.discard_reason = result.discard_reason
                    opp.discarded_by = agent.name
                    # Falhas anteriores ficam registradas mesmo no descarte.
                    if failed_agents:
                        opp.failed_agents = failed_agents
                    log.info(
                        "pipeline.topic.discarded",
                        topic=topic_name,
                        by=agent.name,
                        reason=result.discard_reason,
                    )
                    discarded = True
                    break

            # Rastreia cada agente que o topico passou, para saber exatamente
            # ate onde ele chegou antes de (eventualmente) ser descartado.
            log.info("pipeline.agent.passed", topic=topic_name, agent=agent.name)

        if not discarded:
            if failed_agents:
                opp.status = OpportunityStatus.PARTIAL
                opp.failed_agents = failed_agents
            else:
                opp.status = OpportunityStatus.COMPLETED

        # Fase de escrita (sessao curta): 1 commit por topico, ja com o status
        # final — o banco nunca ve IN_PROGRESS nem linha parcial.
        async with session_factory() as session:
            session.add(opp)
            await session.commit()

        if not discarded:
            log.info(
                "pipeline.topic.completed",
                topic=topic_name,
                opportunity_id=str(opp.id),
                score_total=opp.score_total,
                status=opp.status.value,
                failed_agents=[f["agent"] for f in failed_agents] or None,
            )
        return opp

    async def run_for_idea(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        account_id: uuid.UUID,
        idea: dict,
        profile: dict | None = None,
    ) -> Opportunity:
        """Modo Ideia: analisa um produto/ideia trazido pelo fundador em vez de
        descobrir topicos (pula o Trend Hunter). Roda os mesmos agentes de
        analise; a compatibilidade com o fundador vira INFORMATIVA — nao
        descarta, porque o fundador ja escolheu seguir com a ideia."""
        name = (str(idea.get("name") or "").strip()[:200]) or "Ideia sem nome"
        description = str(idea.get("description") or "").strip()[:2000]
        if profile is None:
            # Fase de leitura (sessao curta); commit porque get_profile semeia.
            async with session_factory() as session:
                profile = profile_to_dict(await get_profile(session, account_id))
                await session.commit()
        topic_data = {
            "name": name,
            "description": description,
            "source": "founder_idea",
            "growth_signal": "n/a",
        }
        log.info("pipeline.run_for_idea.started", idea=name)
        opp = await self._process_topic(
            session_factory,
            account_id,
            topic_data,
            profile,
            source="founder_idea",
            ignore_discard_from={"founder_compatibility"},
        )
        log.info(
            "pipeline.run_for_idea.completed",
            idea=name,
            opportunity_id=str(opp.id),
            status=opp.status.value,
            score_total=opp.score_total,
        )
        return opp


pipeline = Pipeline()
