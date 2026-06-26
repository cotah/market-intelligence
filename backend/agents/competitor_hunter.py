"""Agente 3 - Competitor Hunter.

Para um problema validado, mapeia quem ja resolve: nome, preco,
diferenciais e fraquezas reportadas. Usa Serper + Perplexity como fontes.

Sem criterio de descarte: concorrencia (mesmo forte) e insumo para o
Scorer, nao motivo de eliminacao automatica.
"""

import traceback

from agents.base import AgentResult, BaseAgent, PipelineContext
from core import llm
from core.logging_config import get_logger
from integrations import perplexity, serper

log = get_logger("agents.competitor_hunter")

_SYSTEM = (
    "You map the competitive landscape for a software/SaaS idea. You list "
    "real competitors with pricing and, crucially, the weaknesses users "
    "complain about. Be concrete; do not invent companies."
)


class CompetitorHunterAgent(BaseAgent):
    name = "competitor_hunter"

    async def run(self, context: PipelineContext) -> AgentResult:
        topic = context.topic
        log.info("competitor_hunter.started", topic=topic)

        serper_results = await serper.google_search(
            f"{topic} software tools competitors alternatives pricing", num_results=8
        )
        perplexity_text = await perplexity.search(
            f"Who are the main companies/products solving '{topic}'? "
            "For each, give pricing, key differentiators and the weaknesses users complain about.",
            focus="competitor analysis",
        )

        sources = self._format_sources(serper_results, perplexity_text)

        prompt = f"""Topic: "{topic}"

Map the competitors based on the research below.

RESEARCH:
{sources}

List AT MOST 5 competitors (only the 5 most relevant). Keep each field short.

Return JSON:
{{
  "competitors": [
    {{"name": "...", "pricing": "...", "strengths": ["..."], "weaknesses": ["..."]}}
  ],
  "gaps": ["unmet need or weakness common across competitors"],
  "saturation": "low | medium | high"
}}"""

        # max_tokens menor + no maximo 5 competidores => JSON curto, que nao
        # estoura o limite e nao quebra no parse.
        try:
            data = await llm.ask_json(prompt, system=_SYSTEM, max_tokens=1500)
        except Exception as e:  # noqa: BLE001
            # Concorrencia e insumo do Scorer, nao filtro: mesmo se o parse
            # falhar de vez, seguimos com um resultado VAZIO mas valido em vez
            # de parar o topico.
            log.warning(
                "competitor_hunter.empty_fallback",
                topic=topic,
                error=str(e),
                traceback=traceback.format_exc(),
            )
            data = {"competitors": [], "gaps": []}

        # Normaliza a forma e limita a 5 competidores (o parser pode ter salvo
        # um JSON parcial; aqui garantimos shape consistente para os agentes
        # seguintes).
        if not isinstance(data, dict):
            data = {"competitors": [], "gaps": []}
        data.setdefault("competitors", [])
        data.setdefault("gaps", [])
        if isinstance(data["competitors"], list):
            data["competitors"] = data["competitors"][:5]

        log.info(
            "competitor_hunter.completed",
            topic=topic,
            competitors=len(data["competitors"]) if isinstance(data["competitors"], list) else 0,
        )
        return AgentResult(success=True, data=data)

    @staticmethod
    def _format_sources(serper_results: list[dict], perplexity_text: str) -> str:
        parts: list[str] = []
        if serper_results:
            lines = "\n".join(f"- {r['title']}: {r['snippet']}" for r in serper_results if r.get("title"))
            parts.append(f"[Google / Serper]\n{lines}")
        if perplexity_text:
            parts.append(f"[Perplexity]\n{perplexity_text}")
        if not parts:
            return "(No sources responded. Use general knowledge; if none, return empty competitors list.)"
        return "\n\n".join(parts)
