"""Agente 4 - Market Size.

Estima TAM, SAM e SOM usando dados publicos (Perplexity) + raciocinio do
LLM. Retorna numeros com fonte e crescimento anual estimado.
"""

import traceback

from agents.base import AgentResult, BaseAgent, PipelineContext
from core import llm
from core.logging_config import get_logger
from integrations import perplexity

log = get_logger("agents.market_size")

_SYSTEM = (
    "You are a market sizing analyst. You estimate TAM/SAM/SOM using public "
    "data and clear reasoning. Always state assumptions and cite sources when "
    "available. Prefer ranges over false precision."
)


class MarketSizeAgent(BaseAgent):
    name = "market_size"

    async def run(self, context: PipelineContext) -> AgentResult:
        topic = context.topic
        log.info("market_size.started", topic=topic)

        market_text = await perplexity.search(
            f"Market size data for '{topic}': total addressable market (TAM), industry revenue, "
            "number of potential customers, and annual growth rate. Include figures and sources.",
            focus="market size and industry data",
        )

        prompt = f"""Topic: "{topic}"

Using the market data below (and your knowledge), estimate the market size.

MARKET DATA:
{market_text or "(no external data; estimate from general knowledge and state assumptions)"}

Return JSON:
{{
  "tam": "e.g. $5B global",
  "sam": "serviceable addressable market with reasoning",
  "som": "realistic obtainable market in year 1-2",
  "growth_rate": "e.g. 12% per year",
  "assumptions": ["..."],
  "sources": ["..."]
}}"""

        try:
            data = await llm.ask_json(prompt, system=_SYSTEM, max_tokens=1800)
        except Exception as e:  # noqa: BLE001
            log.error("market_size.failed", topic=topic, error=str(e), traceback=traceback.format_exc())
            return AgentResult(success=False, data={}, error=str(e))

        log.info("market_size.completed", topic=topic)
        return AgentResult(success=True, data=data)
