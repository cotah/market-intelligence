"""Agente 9 - Project Generator.

Ativado apenas quando score >= MIN_SCORE_FOR_PROJECT_PLAN (default 8.0).
Gera plano completo: Business Model Canvas, features do MVP, stack
recomendada, roadmap de 90 dias e estimativa de custo inicial.

Se o score for menor que o minimo, retorna um marcador explicito de skip
({"skipped": true, "reason": ...}) que a pipeline grava em project_plan —
assim o relatorio mostra "pulado por score" em vez de "sem dados".
"""

import json
import traceback

from agents.base import AgentResult, BaseAgent, PipelineContext
from core import llm
from core.config import settings
from core.founder_profile import get_profile_as_text
from core.logging_config import get_logger

log = get_logger("agents.project_generator")

_SYSTEM = (
    "You are a startup co-founder writing a concrete launch plan for a solo "
    "bootstrap founder. Be practical and specific; favor tools the founder "
    "already has. Output a real plan, not generic advice."
)


class ProjectGeneratorAgent(BaseAgent):
    name = "project_generator"

    async def run(self, context: PipelineContext) -> AgentResult:
        topic = context.topic
        total = (context.score_data or {}).get("total", 0) or 0

        if total < settings.min_score_for_project_plan:
            log.info("project_generator.skipped", topic=topic, total=total)
            # Pulo por design, mas NUNCA invisivel: o marcador vai para
            # project_plan e o relatorio mostra o motivo em vez de "sem dados"
            # (que se confunde com falha).
            minimum = settings.min_score_for_project_plan
            return AgentResult(
                success=True,
                data={
                    "skipped": True,
                    "score": total,
                    "min_required": minimum,
                    "reason": (
                        f"Score {total} abaixo do minimo {minimum} — "
                        "plano nao gerado (comportamento esperado)."
                    ),
                },
            )

        log.info("project_generator.started", topic=topic, total=total)

        ctx = {
            "monetization": (context.monetization_data or {}).get("recommended"),
            "ai_role": (context.ai_opportunity_data or {}).get("ai_role"),
            "competitor_gaps": (context.competitor_data or {}).get("gaps", []),
        }

        prompt = f"""{get_profile_as_text()}

BUSINESS IDEA: "{topic}"
Context: {json.dumps(ctx, ensure_ascii=False)}

Generate a complete launch plan. Return JSON:
{{
  "bmc": {{
    "value_proposition": "...",
    "customer_segments": ["..."],
    "channels": ["..."],
    "revenue_streams": ["..."],
    "key_activities": ["..."],
    "key_resources": ["..."],
    "cost_structure": ["..."]
  }},
  "mvp_features": ["must-have feature 1", "..."],
  "recommended_stack": ["..."],
  "roadmap_90_days": [
    {{"phase": "Days 1-30", "goals": ["..."]}},
    {{"phase": "Days 31-60", "goals": ["..."]}},
    {{"phase": "Days 61-90", "goals": ["..."]}}
  ],
  "estimated_initial_cost": "e.g. $200/mo in tools + 0 upfront"
}}"""

        try:
            # Plano completo (BMC + MVP + roadmap de 90 dias) e grande de
            # proposito: truncar um plano de negocio e pior do que truncar uma
            # lista de competidores. A recuperacao de JSON parcial no parser
            # protege contra quebra se ainda assim estourar.
            data = await llm.ask_json(prompt, system=_SYSTEM, max_tokens=2500)
        except Exception as e:  # noqa: BLE001
            log.error("project_generator.failed", topic=topic, error=str(e), traceback=traceback.format_exc())
            return AgentResult(success=False, data={}, error=str(e))

        log.info("project_generator.completed", topic=topic)
        return AgentResult(success=True, data=data)
