"""Testes do orquestrador da pipeline (sem rede/banco: agentes e sessao fakes).

Cobre o fluxo central: mapeamento de dados para os campos JSONB, parada da
cadeia no descarte, score_total, rodada sem topicos e a sinalizacao de
falha parcial (status PARTIAL + failed_agents).
"""

import uuid

from agents.base import AgentResult, BaseAgent, PipelineContext
from core.pipeline import Pipeline
from models import FounderProfile, Opportunity, OpportunityStatus

# Conta dona das rodadas nos testes (multi-tenant).
ACC = uuid.UUID("00000000-0000-0000-0000-000000000001")


class FakeSession:
    """Sessao async minima: simula get/add/flush sem banco real."""

    def __init__(self) -> None:
        self._profiles: dict[uuid.UUID, FounderProfile] = {}
        self.added: list = []

    async def get(self, model, pk):
        if model is FounderProfile:
            return self._profiles.get(pk)
        return None

    def add(self, obj) -> None:
        self.added.append(obj)
        if isinstance(obj, FounderProfile):
            self._profiles[obj.account_id] = obj

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

    opp = await p._process_topic(FakeSession(), ACC, TOPIC)

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

    opp = await p._process_topic(FakeSession(), ACC, TOPIC)

    assert opp.status == OpportunityStatus.DISCARDED
    assert opp.discarded_by == "founder_compatibility"
    assert "30%" in opp.discard_reason
    # O dado do agente que descartou ainda e persistido (rastreabilidade).
    assert opp.compatibility_data == {"score": 30}
    # A cadeia PARA no descarte: o agente seguinte nunca roda.
    assert after.ran is False
    assert opp.monetization_data is None


async def test_project_generator_skip_marker_is_persisted_in_project_plan():
    # Score 6.0-7.9: o Project Generator e pulado POR DESIGN, mas o motivo
    # precisa chegar ao banco (project_plan) em vez de virar "sem dados".
    # Nada falhou, entao o status permanece COMPLETED (nao PARTIAL).
    scorer = FakeAgent("scorer", _ok({"total": 7.0}))
    skip_marker = {
        "skipped": True,
        "score": 7.0,
        "min_required": 8.0,
        "reason": "Score 7.0 abaixo do minimo 8.0 â€” plano nao gerado (comportamento esperado).",
    }
    generator = FakeAgent("project_generator", _ok(skip_marker))
    p = _pipeline_with([scorer, generator])

    opp = await p._process_topic(FakeSession(), ACC, TOPIC)

    assert opp.status == OpportunityStatus.COMPLETED
    assert not opp.failed_agents
    assert opp.project_plan == skip_marker  # visivel no relatorio, nao NULL


async def test_scorer_sets_score_total():
    scorer = FakeAgent("scorer", _ok({"total": 8.7, "market": 9}))
    p = _pipeline_with([scorer])

    opp = await p._process_topic(FakeSession(), ACC, TOPIC)

    assert opp.score_total == 8.7
    assert opp.score_data == {"total": 8.7, "market": 9}


# ------------- Opcao A: selo "Aprovado com ressalvas" (pos-DA) -------------
# docs/PROPOSTA_SCORER_DEVILS_ADVOCATE.md: se o Devil's Advocate lista
# 2+ fatal flaws OU 3+ riscos "high", score_data ganha risk_flag="high".
# A NOTA NUNCA MUDA â€” so o selo.


async def test_devils_advocate_fatal_flaws_set_risk_flag_without_changing_score():
    scorer = FakeAgent("scorer", _ok({"total": 7.0, "market": 8}))
    da = FakeAgent(
        "devils_advocate",
        _ok({"fatal_flaws": ["too generic", "incumbents crush it"], "risks": []}),
    )
    p = _pipeline_with([scorer, da])

    opp = await p._process_topic(FakeSession(), ACC, TOPIC)

    assert opp.status == OpportunityStatus.COMPLETED
    assert opp.score_data["risk_flag"] == "high"
    assert opp.score_total == 7.0  # nota intacta
    assert opp.score_data["total"] == 7.0


async def test_devils_advocate_many_high_risks_set_risk_flag():
    scorer = FakeAgent("scorer", _ok({"total": 7.5}))
    da = FakeAgent(
        "devils_advocate",
        _ok({
            "fatal_flaws": [],
            "risks": [
                {"risk": "a", "severity": "high"},
                {"risk": "b", "severity": "high"},
                {"risk": "c", "severity": "HIGH"},  # case-insensitive
                {"risk": "d", "severity": "low"},
            ],
        }),
    )
    p = _pipeline_with([scorer, da])

    opp = await p._process_topic(FakeSession(), ACC, TOPIC)

    assert opp.score_data["risk_flag"] == "high"


async def test_devils_advocate_calm_does_not_set_risk_flag():
    scorer = FakeAgent("scorer", _ok({"total": 7.0}))
    da = FakeAgent(
        "devils_advocate",
        _ok({"fatal_flaws": ["one flaw"], "risks": [{"risk": "a", "severity": "high"}]}),
    )
    p = _pipeline_with([scorer, da])

    opp = await p._process_topic(FakeSession(), ACC, TOPIC)

    # 1 fatal flaw e 1 risco high: abaixo dos thresholds (2 e 3).
    assert "risk_flag" not in opp.score_data
    assert opp.score_total == 7.0


# ------------------------------- run_once ---------------------------------
async def test_run_once_with_no_topics_returns_empty_summary(monkeypatch):
    p = _pipeline_with([FakeAgent("problem_hunter", _ok())])

    async def no_topics(limit, niche=""):
        return {"topics": []}

    monkeypatch.setattr(p.trend_hunter, "discover_topics", no_topics)

    summary = await p.run_once(FakeSession(), ACC)

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

    async def two_topics(limit, niche=""):
        return {"topics": [{"name": "Good"}, {"name": "Bad"}]}

    monkeypatch.setattr(p.trend_hunter, "discover_topics", two_topics)

    summary = await p.run_once(FakeSession(), ACC)

    assert summary["topics"] == 2
    assert summary["completed"] == 1
    assert summary["discarded"] == 1
    assert summary["discards"] == [
        {"topic": "Bad", "by": "problem_hunter", "reason": "sem dor real"}
    ]
    assert len(summary["opportunity_ids"]) == 2


# --------------------- Falha parcial (PARTIAL + failed_agents) ---------------------
# Comportamento novo: um topico que termina a cadeia com algum agente falho
# NUNCA aparece como COMPLETED "limpo" â€” vira PARTIAL e registra quem falhou.


async def test_topic_with_failed_agent_becomes_partial():
    ok_before = FakeAgent("problem_hunter", _ok({"pain_phrases": ["x"]}))
    failing = FakeAgent(
        "market_size", AgentResult(success=False, data={}, error="LLM down")
    )
    ok_after = FakeAgent("monetization", _ok({"models": ["saas"]}))
    p = _pipeline_with([ok_before, failing, ok_after])

    opp = await p._process_topic(FakeSession(), ACC, TOPIC)

    # A cadeia continua (graceful degradation), mas o resultado e sinalizado.
    assert ok_after.ran is True
    assert opp.status == OpportunityStatus.PARTIAL
    assert opp.failed_agents == [{"agent": "market_size", "error": "LLM down"}]


async def test_topic_with_all_agents_ok_stays_completed_without_failed_agents():
    p = _pipeline_with([FakeAgent("problem_hunter", _ok({"pain_phrases": ["x"]}))])

    opp = await p._process_topic(FakeSession(), ACC, TOPIC)

    assert opp.status == OpportunityStatus.COMPLETED
    assert not opp.failed_agents  # None ou lista vazia â€” nunca falhas fantasma


async def test_failed_agents_recorded_even_when_discarded_later():
    failing = FakeAgent(
        "competitor_hunter", AgentResult(success=False, data={}, error="parse error")
    )
    discarder = FakeAgent(
        "scorer",
        AgentResult(success=True, data={"total": 4.0}, should_discard=True, discard_reason="score baixo"),
    )
    p = _pipeline_with([failing, discarder])

    opp = await p._process_topic(FakeSession(), ACC, TOPIC)

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

    async def one_topic(limit, niche=""):
        return {"topics": [{"name": "Good"}]}

    monkeypatch.setattr(p.trend_hunter, "discover_topics", one_topic)

    summary = await p.run_once(FakeSession(), ACC)

    # PARTIAL nao pode se esconder dentro de "completed".
    assert summary["partial"] == 1
    assert summary["completed"] == 0
    assert summary["discarded"] == 0


# --------------------------- Modo Ideia (run_for_idea) ---------------------------
async def test_run_for_idea_sets_source_and_runs_agents():
    problem = FakeAgent("problem_hunter", _ok({"pain_phrases": ["x"]}))
    p = _pipeline_with([problem])

    opp = await p.run_for_idea(
        FakeSession(), ACC, {"name": "Coleira GPS", "description": "rastreador pet"}, profile={}
    )

    assert opp.source == "founder_idea"
    assert opp.title == "Coleira GPS"
    assert opp.trend_data["source"] == "founder_idea"
    assert opp.problem_data == {"pain_phrases": ["x"]}
    assert opp.status == OpportunityStatus.COMPLETED
    assert problem.ran is True


async def test_run_for_idea_ignores_founder_compatibility_discard():
    problem = FakeAgent("problem_hunter", _ok({"pain_phrases": ["x"]}))
    compat = FakeAgent(
        "founder_compatibility",
        AgentResult(success=True, data={"score": 20}, should_discard=True,
                    discard_reason="compatibilidade baixa"),
    )
    after = FakeAgent("monetization", _ok({"models": ["saas"]}))
    p = _pipeline_with([problem, compat, after])

    opp = await p.run_for_idea(FakeSession(), ACC, {"name": "X", "description": "y"}, profile={})

    # NAO descarta por compatibilidade; a cadeia continua ate o fim.
    assert opp.status != OpportunityStatus.DISCARDED
    assert opp.compatibility_data == {"score": 20}   # dado persistido (informativo)
    assert after.ran is True
    assert opp.monetization_data == {"models": ["saas"]}


async def test_run_for_idea_still_discards_on_other_agents():
    # Outros descartes (ex: problem_hunter sem dor real) AINDA valem no modo ideia.
    problem = FakeAgent(
        "problem_hunter",
        AgentResult(success=True, data={}, should_discard=True, discard_reason="sem dor real"),
    )
    after = FakeAgent("monetization", _ok())
    p = _pipeline_with([problem, after])

    opp = await p.run_for_idea(FakeSession(), ACC, {"name": "X", "description": "y"}, profile={})

    assert opp.status == OpportunityStatus.DISCARDED
    assert opp.discarded_by == "problem_hunter"
    assert after.ran is False
