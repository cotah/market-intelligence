"""Testes do orquestrador da pipeline (sem rede/banco: agentes e sessao fakes).

Cobre o fluxo central: mapeamento de dados para os campos JSONB, parada da
cadeia no descarte, score_total, rodada sem topicos e a sinalizacao de
falha parcial (status PARTIAL + failed_agents).
"""

import uuid

from agents.base import AgentResult, BaseAgent, PipelineContext
from core.pipeline import Pipeline
from models import FounderProfile, Opportunity, OpportunityStatus


class FakeSession:
    """Sessao async minima: simula get/add/flush sem banco real."""

    def __init__(self) -> None:
        self._profiles: dict[int, FounderProfile] = {}
        self.added: list = []

    async def get(self, model, pk):
        if model is FounderProfile:
            return self._profiles.get(pk)
        return None

    def add(self, obj) -> None:
        self.added.append(obj)
        if isinstance(obj, FounderProfile):
            self._profiles[obj.id] = obj

    async def flush(self) -> None:
        # Simula o default=uuid.uuid4 aplicado pelo banco no INSERT.
        for obj in self.added:
            if isinstance(obj, Opportunity) and obj.id is None:
                obj.id = uuid.uuid4()


class FakeAgent(BaseAgent):
    """Agente com resultado fixo; registra se rodou e o contexto que viu."""

    def __init__(self, name: str, result: AgentResult) -> None:
        self.name = name
        self._result = result
        self.ran = False
        self.seen_context: PipelineContext | None = None

    async def run(self, context: PipelineContext) -> AgentResult:
        self.ran = True
        self.seen_context = context
        return self._result


def _ok(data: dict | None = None) -> AgentResult:
    return AgentResult(success=True, data=data or {})


def _pipeline_with(agents: list[BaseAgent]) -> Pipeline:
    p = Pipeline()
    p.agents = agents
    return p


TOPIC = {"name": "AI Receptionist", "growth_signal": "high"}


# --------------------------- Mapeamento de dados ---------------------------
async def test_process_topic_completes_and_maps_data_to_jsonb_fields():
    problem = FakeAgent("problem_hunter", _ok({"pain_phrases": ["I hate calls"]}))
    competitor = FakeAgent("competitor_hunter", _ok({"competitors": [{"name": "A"}]}))
    p = _pipeline_with([problem, competitor])

    opp = await p._process_topic(FakeSession(), TOPIC)

    assert opp.status == OpportunityStatus.COMPLETED
    assert opp.trend_data == TOPIC
    assert opp.problem_data == {"pain_phrases": ["I hate calls"]}
    assert opp.competitor_data == {"competitors": [{"name": "A"}]}
    # O dado do agente anterior fica disponivel no contexto do seguinte.
    assert competitor.seen_context.problem_data == {"pain_phrases": ["I hate calls"]}


async def test_process_topic_discard_stops_chain():
    first = FakeAgent("problem_hunter", _ok({"pain_phrases": ["x"] * 5}))
    discarder = FakeAgent(
        "founder_compatibility",
        AgentResult(
            success=True,
            data={"score": 30},
            should_discard=True,
            discard_reason="Compatibilidade 30% abaixo do minimo",
        ),
    )
    after = FakeAgent("monetization", _ok({"models": ["saas"]}))
    p = _pipeline_with([first, discarder, after])

    opp = await p._process_topic(FakeSession(), TOPIC)

    assert opp.status == OpportunityStatus.DISCARDED
    assert opp.discarded_by == "founder_compatibility"
    assert "30%" in opp.discard_reason
    # O dado do agente que descartou ainda e persistido (rastreabilidade).
    assert opp.compatibility_data == {"score": 30}
    # A cadeia PARA no descarte: o agente seguinte nunca roda.
    assert after.ran is False
    assert opp.monetization_data is None


async def test_scorer_sets_score_total():
    scorer = FakeAgent("scorer", _ok({"total": 8.7, "market": 9}))
    p = _pipeline_with([scorer])

    opp = await p._process_topic(FakeSession(), TOPIC)

    assert opp.score_total == 8.7
    assert opp.score_data == {"total": 8.7, "market": 9}


# ------------------------------- run_once ---------------------------------
async def test_run_once_with_no_topics_returns_empty_summary(monkeypatch):
    p = _pipeline_with([FakeAgent("problem_hunter", _ok())])

    async def no_topics(limit):
        return {"topics": []}

    monkeypatch.setattr(p.trend_hunter, "discover_topics", no_topics)

    summary = await p.run_once(FakeSession())

    assert summary["topics"] == 0
    assert summary["completed"] == 0
    assert summary["discarded"] == 0
    assert summary["opportunity_ids"] == []


async def test_run_once_counts_completed_and_discarded(monkeypatch):
    class TopicSensitiveAgent(BaseAgent):
        name = "problem_hunter"

        async def run(self, context: PipelineContext) -> AgentResult:
            if context.topic == "Bad":
                return AgentResult(
                    success=True, data={}, should_discard=True, discard_reason="sem dor real"
                )
            return _ok({"pain_phrases": ["x"]})

    p = _pipeline_with([TopicSensitiveAgent()])

    async def two_topics(limit):
        return {"topics": [{"name": "Good"}, {"name": "Bad"}]}

    monkeypatch.setattr(p.trend_hunter, "discover_topics", two_topics)

    summary = await p.run_once(FakeSession())

    assert summary["topics"] == 2
    assert summary["completed"] == 1
    assert summary["discarded"] == 1
    assert summary["discards"] == [
        {"topic": "Bad", "by": "problem_hunter", "reason": "sem dor real"}
    ]
    assert len(summary["opportunity_ids"]) == 2


# --------------------- Falha parcial (PARTIAL + failed_agents) ---------------------
# Comportamento novo: um topico que termina a cadeia com algum agente falho
# NUNCA aparece como COMPLETED "limpo" — vira PARTIAL e registra quem falhou.


async def test_topic_with_failed_agent_becomes_partial():
    ok_before = FakeAgent("problem_hunter", _ok({"pain_phrases": ["x"]}))
    failing = FakeAgent(
        "market_size", AgentResult(success=False, data={}, error="LLM down")
    )
    ok_after = FakeAgent("monetization", _ok({"models": ["saas"]}))
    p = _pipeline_with([ok_before, failing, ok_after])

    opp = await p._process_topic(FakeSession(), TOPIC)

    # A cadeia continua (graceful degradation), mas o resultado e sinalizado.
    assert ok_after.ran is True
    assert opp.status == OpportunityStatus.PARTIAL
    assert opp.failed_agents == [{"agent": "market_size", "error": "LLM down"}]


async def test_topic_with_all_agents_ok_stays_completed_without_failed_agents():
    p = _pipeline_with([FakeAgent("problem_hunter", _ok({"pain_phrases": ["x"]}))])

    opp = await p._process_topic(FakeSession(), TOPIC)

    assert opp.status == OpportunityStatus.COMPLETED
    assert not opp.failed_agents  # None ou lista vazia — nunca falhas fantasma


async def test_failed_agents_recorded_even_when_discarded_later():
    failing = FakeAgent(
        "competitor_hunter", AgentResult(success=False, data={}, error="parse error")
    )
    discarder = FakeAgent(
        "scorer",
        AgentResult(success=True, data={"total": 4.0}, should_discard=True, discard_reason="score baixo"),
    )
    p = _pipeline_with([failing, discarder])

    opp = await p._process_topic(FakeSession(), TOPIC)

    # Descarte continua mandando no status final...
    assert opp.status == OpportunityStatus.DISCARDED
    # ...mas a falha anterior fica registrada para rastreabilidade.
    assert opp.failed_agents == [{"agent": "competitor_hunter", "error": "parse error"}]


async def test_run_once_counts_partial_separately(monkeypatch):
    class FailingAgent(BaseAgent):
        name = "market_size"

        async def run(self, context: PipelineContext) -> AgentResult:
            return AgentResult(success=False, data={}, error="boom")

    p = _pipeline_with([FailingAgent()])

    async def one_topic(limit):
        return {"topics": [{"name": "Good"}]}

    monkeypatch.setattr(p.trend_hunter, "discover_topics", one_topic)

    summary = await p.run_once(FakeSession())

    # PARTIAL nao pode se esconder dentro de "completed".
    assert summary["partial"] == 1
    assert summary["completed"] == 0
    assert summary["discarded"] == 0
