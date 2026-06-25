"""Agente 8 - Scorer.

Pede ao LLM uma nota 0-10 por dimensao e calcula o total ponderado em
Python (mais confiavel que pedir a conta ao LLM).

Pesos:
  - Mercado (market)          20%
  - Concorrencia (competition)15%
  - Facilidade (ease)         15%
  - Escalabilidade (scalability)15%
  - Potencial de IA (ai_potential)20%
  - Lucro (profit)            15%

Criterio de descarte: total < MIN_SCORE_TO_KEEP (default 6.0).
"""

import json

from agents.base import AgentResult, BaseAgent, PipelineContext
from core import llm
from core.config import settings
from core.logging_config import get_logger

log = get_logger("agents.scorer")

# Pesos por dimensao (somam 100).
_WEIGHTS: dict[str, int] = {
    "market": 20,
    "competition": 15,
    "ease": 15,
    "scalability": 15,
    "ai_potential": 20,
    "profit": 15,
}

_SYSTEM = (
    "You score a business opportunity across fixed dimensions, each 0-10. "
    "Be calibrated and critical: a 9-10 means exceptional, 5 is average. "
    "Use all the context provided."
)


class ScorerAgent(BaseAgent):
    name = "scorer"

    async def run(self, context: PipelineContext) -> AgentResult:
        topic = context.topic
        log.info("scorer.started", topic=topic)

        ctx_block = self._context_block(context)

        prompt = f"""Topic: "{topic}"

CONTEXT FROM PREVIOUS AGENTS:
{ctx_block}

Score each dimension from 0 to 10. Return JSON with EXACTLY these keys:
{{
  "market": 0-10,
  "competition": 0-10,
  "ease": 0-10,
  "scalability": 0-10,
  "ai_potential": 0-10,
  "profit": 0-10,
  "reasoning": "one short paragraph"
}}"""

        try:
            raw = await llm.ask_json(prompt, system=_SYSTEM, max_tokens=1200)
        except Exception as e:  # noqa: BLE001
            log.error("scorer.failed", topic=topic, error=str(e))
            return AgentResult(
                success=False,
                should_discard=True,
                discard_reason=f"Scorer falhou ao pontuar: {e}",
                error=str(e),
            )

        dims = {key: self._clamp(raw.get(key)) for key in _WEIGHTS}
        total = round(sum(dims[key] * weight for key, weight in _WEIGHTS.items()) / 100, 2)

        data = {**dims, "total": total, "reasoning": raw.get("reasoning", "") if isinstance(raw, dict) else ""}

        if total < settings.min_score_to_keep:
            reason = f"Score baixo: {total} (minimo {settings.min_score_to_keep})."
            log.info("scorer.discarded", topic=topic, total=total)
            return AgentResult(success=True, data=data, should_discard=True, discard_reason=reason)

        log.info("scorer.completed", topic=topic, total=total)
        return AgentResult(success=True, data=data)

    @staticmethod
    def _clamp(value: object) -> float:
        try:
            v = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(10.0, v))

    @staticmethod
    def _context_block(context: PipelineContext) -> str:
        def short(d: dict | None, *keys: str) -> dict:
            d = d or {}
            return {k: d.get(k) for k in keys if k in d}

        summary = {
            "problem": short(context.problem_data, "pain_phrases", "has_real_pain"),
            "competitors": short(context.competitor_data, "saturation", "gaps"),
            "market": short(context.market_data, "tam", "som", "growth_rate"),
            "ai": short(context.ai_opportunity_data, "verdict", "ai_role"),
            "compatibility": short(context.compatibility_data, "score", "time_to_mvp"),
            "monetization": short(context.monetization_data, "recommended"),
        }
        return json.dumps(summary, ensure_ascii=False, indent=2)


WEIGHTS = _WEIGHTS
