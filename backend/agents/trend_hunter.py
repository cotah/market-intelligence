"""Agente 1 - Trend Hunter.

Encontra assuntos que estao crescendo agora, combinando Serper (Google),
Grok (X/Twitter) e Perplexity (Product Hunt, Hacker News), e consolida
tudo com o LLM em uma lista de 5-10 topicos com sinal de crescimento.

Funciona mesmo se uma integracao falhar (graceful degradation): se
nenhuma fonte responder, ainda pedimos topicos ao LLM com o que houver.
"""

from datetime import date

from agents.base import AgentResult, BaseAgent, PipelineContext
from core import llm
from core.exceptions import AgentException
from core.logging_config import get_logger
from integrations import grok, perplexity, serper

log = get_logger("agents.trend_hunter")

_SYSTEM = (
    "You are a trend analyst that finds emerging business opportunities. "
    "You identify topics that are growing in interest RIGHT NOW and could "
    "become viable software/SaaS businesses."
)


class TrendHunterAgent(BaseAgent):
    name = "trend_hunter"

    async def discover_topics(self, limit: int = 5) -> dict:
        """Descobre topicos em alta. Retorna {"topics": [...]}."""
        month = date.today().strftime("%B %Y")
        log.info("trend_hunter.started", month=month, limit=limit)

        # 1. Fontes (cada uma degrada graciosamente para vazio).
        serper_results = await serper.google_search(
            f"trending startup ideas and growing markets {month}", num_results=8
        )
        grok_text = await grok.search_x(
            f"What new tools, problems or product categories are people excited about on X in {month}? "
            "Focus on things that could become a software business."
        )
        ph_hn_text = await perplexity.search(
            f"What are the trending products on Product Hunt and top discussions on Hacker News in {month}? "
            "List concrete product categories and emerging needs.",
            focus="Product Hunt and Hacker News",
        )

        sources_block = self._format_sources(serper_results, grok_text, ph_hn_text)

        # 2. Consolidacao via LLM.
        prompt = f"""Based on the research below, identify {limit} to {min(limit + 5, 10)} business topics/categories
that are growing RIGHT NOW and could become a software or SaaS business.

RESEARCH DATA:
{sources_block}

Return a JSON object with this exact shape:
{{
  "topics": [
    {{
      "name": "short topic name (e.g. 'AI Receptionist')",
      "growth_signal": "high | medium | low",
      "sources": ["X/Twitter", "Product Hunt", ...],
      "evidence": "one sentence on why this is growing",
      "search_volume_trend": "increasing | stable | unknown"
    }}
  ]
}}"""

        try:
            data = await llm.ask_json(prompt, system=_SYSTEM, max_tokens=2000, temperature=0.4)
        except Exception as e:
            log.error("trend_hunter.failed", error=str(e))
            raise AgentException(f"TrendHunter failed to consolidate topics: {e}") from e

        topics = data.get("topics", []) if isinstance(data, dict) else []
        topic_names = [t.get("name", "?") for t in topics if isinstance(t, dict)]
        log.info("trend_hunter.completed", topics_count=len(topics), topics=topic_names)
        if not topics:
            log.warning(
                "trend_hunter.no_topics",
                hint="LLM nao retornou topicos. Fontes podem ter vindo vazias.",
            )
        return {"topics": topics}

    async def run(self, context: PipelineContext) -> AgentResult:
        """Conforma com a interface base.

        Na pipeline, os topicos vem de `discover_topics`. Aqui apenas
        garantimos que o contexto carrega trend_data para o topico atual.
        """
        if context.trend_data:
            return AgentResult(success=True, data=context.trend_data)

        # Caso seja chamado sem trend_data pre-carregada, descobrimos e
        # tentamos casar com o topico do contexto.
        result = await self.discover_topics()
        match = next(
            (t for t in result["topics"] if t.get("name", "").lower() == context.topic.lower()),
            None,
        )
        if match is None:
            match = {"name": context.topic, "growth_signal": "unknown", "sources": [], "evidence": ""}
        return AgentResult(success=True, data=match)

    @staticmethod
    def _format_sources(serper_results: list[dict], grok_text: str, ph_hn_text: str) -> str:
        parts: list[str] = []

        if serper_results:
            lines = "\n".join(
                f"- {r['title']}: {r['snippet']}" for r in serper_results if r.get("title")
            )
            parts.append(f"[Google / Serper]\n{lines}")

        if grok_text:
            parts.append(f"[X / Twitter via Grok]\n{grok_text}")

        if ph_hn_text:
            parts.append(f"[Product Hunt / Hacker News via Perplexity]\n{ph_hn_text}")

        if not parts:
            return "(No external sources responded. Use your general knowledge of current tech/business trends.)"

        return "\n\n".join(parts)
