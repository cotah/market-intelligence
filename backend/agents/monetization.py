"""Agente 7 - Monetization.

Define os modelos de monetizacao viaveis (assinatura, marketplace,
comissao, ads, licenca, white label, hardware, API) e recomenda os 2
melhores com estimativa de ticket medio.
"""

import json
import traceback

from agents.base import AgentResult, BaseAgent, PipelineContext
from core import llm
from core.logging_config import get_logger

log = get_logger("agents.monetization")

_SYSTEM = (
    "You design monetization strategy for a SaaS/software idea. Choose from: "
    "subscription, marketplace, commission, ads, license, white_label, hardware, api. "
    "Recommend the 2 best fits with a realistic average ticket."
)


class MonetizationAgent(BaseAgent):
    name = "monetization"

    async def run(self, context: PipelineContext) -> AgentResult:
        topic = context.topic
        log.info("monetization.started", topic=topic)

        market = context.market_data or {}

        prompt = f"""Topic: "{topic}"
Market context: TAM={market.get("tam", "n/a")}, growth={market.get("growth_rate", "n/a")}
Competitors context: {json.dumps((context.competitor_data or {}).get("competitors", [])[:3], ensure_ascii=False)}

Return JSON:
{{
  "models": [
    {{"model": "subscription", "avg_ticket": "e.g. $49/mo", "reasoning": "..."}}
  ],
  "recommended": "subscription",
  "notes": "short note on pricing strategy"
}}
Include the top 2 models in "models"."""

        try:
            data = await llm.ask_json(prompt, system=_SYSTEM, max_tokens=1400)
        except Exception as e:  # noqa: BLE001
            log.error("monetization.failed", topic=topic, error=str(e), traceback=traceback.format_exc())
            return AgentResult(success=False, data={}, error=str(e))

        log.info("monetization.completed", topic=topic, recommended=data.get("recommended") if isinstance(data, dict) else None)
        return AgentResult(success=True, data=data)
