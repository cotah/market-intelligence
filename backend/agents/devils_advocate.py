"""Agente 10 - Devil's Advocate.

Tenta destruir a ideia de proposito: por que vai falhar, por que ninguem
compra, qual concorrente mata isso, qual risco regulatorio. Retorna riscos
com severidade. Nao descarta (informa, evita paixao cega).
"""

import json
import traceback

from agents.base import AgentResult, BaseAgent, PipelineContext
from core import llm
from core.logging_config import get_logger

log = get_logger("agents.devils_advocate")

_SYSTEM = (
    "You are a ruthless skeptic investor. Your job is to find every reason this "
    "idea fails: no demand, incumbents crush it, regulation, distribution, unit "
    "economics. Be specific and harsh, but fair."
)


class DevilsAdvocateAgent(BaseAgent):
    name = "devils_advocate"

    async def run(self, context: PipelineContext) -> AgentResult:
        topic = context.topic
        log.info("devils_advocate.started", topic=topic)

        ctx = {
            "competitors": (context.competitor_data or {}).get("competitors", [])[:3],
            "market": (context.market_data or {}).get("tam"),
            "score": (context.score_data or {}).get("total"),
        }

        prompt = f"""Topic: "{topic}"
Context: {json.dumps(ctx, ensure_ascii=False)}

Try to KILL this idea. Return JSON:
{{
  "risks": [{{"risk": "...", "severity": "high | medium | low"}}],
  "fatal_flaws": ["risks that could kill the business entirely"],
  "why_nobody_buys": "...",
  "verdict": "one line: is this worth pursuing despite the risks?"
}}"""

        try:
            data = await llm.ask_json(prompt, system=_SYSTEM, max_tokens=1500)
        except Exception as e:  # noqa: BLE001
            log.error("devils_advocate.failed", topic=topic, error=str(e), traceback=traceback.format_exc())
            return AgentResult(success=False, data={}, error=str(e))

        log.info(
            "devils_advocate.completed",
            topic=topic,
            fatal_flaws=len(data.get("fatal_flaws", [])) if isinstance(data, dict) else 0,
        )
        return AgentResult(success=True, data=data)
