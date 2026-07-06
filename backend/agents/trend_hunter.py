"""Agente 1 - Trend Hunter.

Encontra assuntos que estao crescendo agora, combinando Serper (Google),
Grok (X/Twitter), Perplexity (Product Hunt) e Hacker News (API direta),
e consolida tudo com o LLM em uma lista de 5-10 topicos com sinal de
crescimento. Depois da consolidacao, o Google Trends valida cada topico
com dado real de busca (quando disponivel, sobrescreve a estimativa do LLM).

Funciona mesmo se uma integracao falhar (graceful degradation): se
nenhuma fonte responder, ainda pedimos topicos ao LLM com o que houver.
"""

import traceback
from datetime import date

from agents.base import AgentResult, BaseAgent, PipelineContext
from core import llm
from core.exceptions import AgentException
from core.logging_config import get_logger
from core.text import to_hashtag
from integrations import google_trends, grok, hackernews, perplexity, serper

log = get_logger("agents.trend_hunter")

# trend_direction do Google Trends -> (search_volume_trend, growth_signal).
_TREND_MAP = {
    "rising": ("increasing", "high"),
    "stable": ("stable", "medium"),
    "falling": ("decreasing", "low"),
}

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
        # HN agora vem direto da API oficial; o Perplexity foca so em Product Hunt.
        ph_text = await perplexity.search(
            f"What are the trending products on Product Hunt in {month}? "
            "List concrete product categories and emerging needs.",
            focus="Product Hunt",
        )
        hn_stories = await hackernews.get_top_stories(limit=10)

        sources_block = self._format_sources(serper_results, grok_text, ph_text, hn_stories)

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
      "hashtag": "a SHORT, REAL hashtag people actually use on Instagram/TikTok for this topic (e.g. 'aiagents', 'smallbusiness'). Lowercase, letters and digits only, no spaces or symbols. Prefer popular broad hashtags over invented long ones.",
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
            log.error("trend_hunter.failed", error=str(e), traceback=traceback.format_exc())
            raise AgentException(f"TrendHunter failed to consolidate topics: {e}") from e

        # Loga a forma EXATA do que o LLM devolveu, para flagrar quando o JSON
        # vem certo mas sem a chave "topics" (ou com outro formato).
        log.info(
            "trend_hunter.llm_result",
            result_type=type(data).__name__,
            keys=list(data.keys()) if isinstance(data, dict) else None,
            raw_preview=str(data)[:800],
        )

        topics = data.get("topics", []) if isinstance(data, dict) else []

        # 3. Normaliza a hashtag de cada topico (o LLM pode mandar "#", caixa
        # alta ou simbolos); se faltar, deriva do name sanitizado. E ela que o
        # problem_hunter usa nas buscas de Instagram/TikTok.
        for topic in topics:
            if not isinstance(topic, dict):
                continue
            topic["hashtag"] = to_hashtag(topic.get("hashtag") or topic.get("name") or "")

        # 4. Validacao com dado real do Google Trends (quando disponivel).
        await self._enrich_with_google_trends(topics)

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
    async def _enrich_with_google_trends(topics: list[dict]) -> None:
        """Sobrescreve a estimativa do LLM com dado real do Google Trends.

        Sequencial de proposito: a pytrends raspa o Google e chamadas em
        paralelo aumentam muito a chance de rate limit (429). Topico sem
        dado real (None) mantem a estimativa do LLM.
        """
        for topic in topics:
            if not isinstance(topic, dict) or not topic.get("name"):
                continue
            score = await google_trends.get_trend_score(topic["name"])
            if not score:
                continue
            mapped = _TREND_MAP.get(score.get("trend_direction", ""))
            if not mapped:
                continue
            topic["search_volume_trend"], topic["growth_signal"] = mapped
            sources = topic.setdefault("sources", [])
            if "Google Trends" not in sources:
                sources.append("Google Trends")

    @staticmethod
    def _format_sources(
        serper_results: list[dict],
        grok_text: str,
        ph_text: str,
        hn_stories: list[dict],
    ) -> str:
        parts: list[str] = []

        if serper_results:
            lines = "\n".join(
                f"- {r['title']}: {r['snippet']}" for r in serper_results if r.get("title")
            )
            parts.append(f"[Google / Serper]\n{lines}")

        if grok_text:
            parts.append(f"[X / Twitter via Grok]\n{grok_text}")

        if ph_text:
            parts.append(f"[Product Hunt via Perplexity]\n{ph_text}")

        if hn_stories:
            lines = "\n".join(
                f"- ({s['score']} points, {s['num_comments']} comments) {s['title']}"
                for s in hn_stories
                if s.get("title")
            )
            parts.append(f"[Hacker News - top stories]\n{lines}")

        if not parts:
            return "(No external sources responded. Use your general knowledge of current tech/business trends.)"

        return "\n\n".join(parts)
