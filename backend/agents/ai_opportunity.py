"""Agente 5 - AI Opportunity.

Avalia se o problema pode ser resolvido com IA: SIM / NAO / PARCIALMENTE,
com justificativa e qual parte da solucao a IA executa.
"""

import json

from agents.base import AgentResult, BaseAgent, PipelineContext
from core import llm
from core.logging_config import get_logger

log = get_logger("agents.ai_opportunity")

_SYSTEM = (
    "You assess whether a problem can realistically be solved with AI/LLMs "
    "today. Be honest: many problems only need AI for part of the solution. "
    "Verdict must be one of YES, NO, PARTIALLY."
)


class AIOpportunityAgent(BaseAgent):
    name = "ai_opportunity"

    async def run(self, context: PipelineContext) -> AgentResult:
        topic = context.topic
        log.info("ai_opportunity.started", topic=topic)

        problem_summary = self._summarize(context.problem_data)

        prompt = f"""Topic: "{topic}"

Validated problem context:
{problem_summary}

Can AI (LLMs, automation, ML) solve this problem? Return JSON:
{{
  "verdict": "YES | NO | PARTIALLY",
  "reasoning": "why",
  "ai_role": "which specific part of the solution AI executes",
  "non_ai_parts": ["parts that still need humans or classic software"]
}}"""

        try:
            data = await llm.ask_json(prompt, system=_SYSTEM, max_tokens=1200)
        except Exception as e:  # noqa: BLE001
            log.error("ai_opportunity.failed", topic=topic, error=str(e))
            return AgentResult(success=False, data={}, error=str(e))

        log.info("ai_opportunity.completed", topic=topic, verdict=data.get("verdict") if isinstance(data, dict) else None)
        return AgentResult(success=True, data=data)

    @staticmethod
    def _summarize(problem_data: dict | None) -> str:
        if not problem_data:
            return "(no problem data)"
        phrases = problem_data.get("pain_phrases", [])
        return "Pain points: " + json.dumps(phrases[:5], ensure_ascii=False)
