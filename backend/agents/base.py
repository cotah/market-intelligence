"""Contratos base dos agentes da pipeline.

`PipelineContext` carrega o estado compartilhado conforme os agentes rodam
em sequencia. Cada agente recebe o contexto, faz seu trabalho e devolve um
`AgentResult` indicando sucesso, dados e se a ideia deve ser descartada.
"""

from dataclasses import dataclass, field


@dataclass
class PipelineContext:
    """Contexto compartilhado entre todos os agentes na pipeline."""

    topic: str  # Topico sendo analisado
    opportunity_id: str  # ID no banco

    trend_data: dict | None = None
    problem_data: dict | None = None
    competitor_data: dict | None = None
    market_data: dict | None = None
    ai_opportunity_data: dict | None = None
    compatibility_data: dict | None = None
    monetization_data: dict | None = None
    score_data: dict | None = None
    project_plan: dict | None = None
    devils_advocate_data: dict | None = None

    should_discard: bool = False
    discard_reason: str = ""


@dataclass
class AgentResult:
    success: bool
    data: dict = field(default_factory=dict)
    should_discard: bool = False
    discard_reason: str = ""
    error: str = ""


class BaseAgent:
    """Classe base. Todo agente define `name` e implementa `run`."""

    name: str = "base"

    async def run(self, context: PipelineContext) -> AgentResult:
        raise NotImplementedError
