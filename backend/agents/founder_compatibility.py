"""Agente 6 - Founder Compatibility.

Compara o problema com o perfil do fundador: skills necessarias vs
disponiveis, gap de conhecimento, tempo estimado de MVP.

Criterio de descarte: compatibilidade < 50%.
"""

import json

from agents.base import AgentResult, BaseAgent, PipelineContext
from core import llm
from core.founder_profile import default_profile_dict, profile_to_text
from core.logging_config import get_logger

log = get_logger("agents.founder_compatibility")

_MIN_COMPATIBILITY = 50

_SYSTEM = (
    "You evaluate how well a business idea fits a specific founder's profile. "
    "Be realistic about skill gaps and time-to-MVP for a solo bootstrap founder. "
    "Geography matters: an opportunity aligned with the founder's current "
    "country or active markets is more executable (local presence, network, "
    "regulatory familiarity). Score is 0-100."
)


class FounderCompatibilityAgent(BaseAgent):
    name = "founder_compatibility"

    async def run(self, context: PipelineContext) -> AgentResult:
        topic = context.topic
        log.info("founder_compatibility.started", topic=topic)

        ai_role = ""
        if context.ai_opportunity_data:
            ai_role = context.ai_opportunity_data.get("ai_role", "")

        # Perfil vem do banco (carregado pela pipeline); fallback no default.
        profile = context.founder_profile or default_profile_dict()
        country = profile.get("current_country", "") or "n/a"
        markets = ", ".join(profile.get("active_markets", []) or []) or "n/a"
        ai_tools = ", ".join(profile.get("ai_tools", []) or []) or "n/a"
        software_tools = ", ".join(profile.get("software_tools", []) or []) or "n/a"
        hardware_tools = ", ".join(profile.get("hardware_tools", []) or []) or "n/a"

        prompt = f"""{profile_to_text(profile)}

BUSINESS IDEA: "{topic}"
How AI is involved: {ai_role or "n/a"}
Problem context: {json.dumps((context.problem_data or {}).get("pain_phrases", [])[:3], ensure_ascii=False)}

GEOGRAPHIC WEIGHTING (apply this when scoring):
- The founder is currently based in: {country}
- Active markets: {markets}
- If this opportunity targets or fits the founder's current country or active
  markets, INCREASE the score (local presence, network, regulatory know-how).
- If it requires being in a market the founder is NOT in, LOWER the score.

FOUNDER TOOLING (what the founder can already build and ship with):
- AI tools: {ai_tools}
- Software / infrastructure: {software_tools}
- Hardware & equipment: {hardware_tools}
- If the idea can be built mostly with tools the founder ALREADY has, raise
  available_knowledge_pct and shorten time_to_mvp. If it needs AI/software/hardware
  the founder lacks, increase the gap and lengthen time_to_mvp.

Evaluate fit for THIS founder. Return JSON:
{{
  "score": 0-100,
  "available_knowledge_pct": 0-100,
  "gap": 0-100,
  "time_to_mvp": "e.g. 2 months",
  "geographic_fit": "high | medium | low",
  "missing_skills": ["..."],
  "reasoning": "short"
}}"""

        try:
            data = await llm.ask_json(prompt, system=_SYSTEM, max_tokens=1200)
        except Exception as e:  # noqa: BLE001
            # Sem avaliacao de fit nao da para seguir com confianca: descarta com motivo.
            log.error("founder_compatibility.failed", topic=topic, error=str(e))
            return AgentResult(
                success=False,
                should_discard=True,
                discard_reason=f"Founder Compatibility falhou: {e}",
                error=str(e),
            )

        score = self._as_int(data.get("score")) if isinstance(data, dict) else 0

        if score < _MIN_COMPATIBILITY:
            reason = f"Compatibilidade baixa: {score}% (minimo {_MIN_COMPATIBILITY}%)."
            log.info("founder_compatibility.discarded", topic=topic, score=score)
            return AgentResult(success=True, data=data, should_discard=True, discard_reason=reason)

        log.info("founder_compatibility.completed", topic=topic, score=score)
        return AgentResult(success=True, data=data)

    @staticmethod
    def _as_int(value: object) -> int:
        try:
            return int(float(value))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0


MIN_COMPATIBILITY = _MIN_COMPATIBILITY
