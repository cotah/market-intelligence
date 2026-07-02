"""Testes dos agentes, com integracoes e LLM mockados (sem rede)."""

import pytest

from agents.base import PipelineContext
from agents.founder_compatibility import FounderCompatibilityAgent
from agents.problem_hunter import MIN_PAIN_EVIDENCES, ProblemHunterAgent
from agents.project_generator import ProjectGeneratorAgent
from agents.scorer import ScorerAgent
from agents.trend_hunter import TrendHunterAgent


def _ctx(topic: str = "AI Receptionist") -> PipelineContext:
    return PipelineContext(topic=topic, opportunity_id="test-id")


# ----------------------------- Problem Hunter -----------------------------
@pytest.fixture
def patch_problem_sources(monkeypatch):
    """Mocka Perplexity e Reddit do Problem Hunter."""
    import agents.problem_hunter as ph

    async def fake_perplexity(query, focus="internet"):
        return "Users complain a lot about this."

    async def fake_reddit(subreddit, query):
        return [{"title": "I hate X", "body": "...", "upvotes": 10, "subreddit": "all", "is_mock": True}]

    monkeypatch.setattr(ph.perplexity, "search", fake_perplexity)
    monkeypatch.setattr(ph.reddit, "search_reddit", fake_reddit)


async def test_problem_hunter_discards_with_few_evidences(monkeypatch, patch_problem_sources):
    import agents.problem_hunter as ph

    async def fake_ask_json(*args, **kwargs):
        return {"pain_phrases": ["only one"], "problems": [], "sources": [], "has_real_pain": False}

    monkeypatch.setattr(ph.llm, "ask_json", fake_ask_json)

    result = await ProblemHunterAgent().run(_ctx())
    assert result.should_discard is True
    assert "evidencia" in result.discard_reason.lower()


async def test_problem_hunter_passes_with_enough_evidences(monkeypatch, patch_problem_sources):
    import agents.problem_hunter as ph

    phrases = [f"pain {i}" for i in range(MIN_PAIN_EVIDENCES + 1)]

    async def fake_ask_json(*args, **kwargs):
        return {"pain_phrases": phrases, "problems": [], "sources": ["Reddit"], "has_real_pain": True}

    monkeypatch.setattr(ph.llm, "ask_json", fake_ask_json)

    result = await ProblemHunterAgent().run(_ctx())
    assert result.should_discard is False
    assert result.success is True
    assert len(result.data["pain_phrases"]) == MIN_PAIN_EVIDENCES + 1


async def test_problem_hunter_discards_gracefully_on_llm_error(monkeypatch, patch_problem_sources):
    import agents.problem_hunter as ph

    async def boom(*args, **kwargs):
        raise RuntimeError("LLM down")

    monkeypatch.setattr(ph.llm, "ask_json", boom)

    result = await ProblemHunterAgent().run(_ctx())
    # Apos o fix: uma falha de LLM nao quebra com erro cru. Cai para um
    # resultado vazio mas valido (success=True) e o criterio normal descarta
    # por falta de evidencia de dor.
    assert result.should_discard is True
    assert result.success is True
    assert "evidencia" in result.discard_reason.lower()
    assert result.data["pain_phrases"] == []


# ------------------------------ Trend Hunter ------------------------------
async def test_trend_hunter_discover_topics(monkeypatch):
    import agents.trend_hunter as th

    async def fake_serper(query, num_results=10):
        return [{"title": "AI tools", "link": "x", "snippet": "growing fast"}]

    async def fake_grok(query):
        return "People love AI receptionists."

    async def fake_perplexity(query, focus="internet"):
        return "Product Hunt is full of AI scheduling tools."

    async def fake_ask_json(*args, **kwargs):
        return {"topics": [{"name": "AI Receptionist", "growth_signal": "high", "sources": ["X/Twitter"], "evidence": "...", "search_volume_trend": "increasing"}]}

    monkeypatch.setattr(th.serper, "google_search", fake_serper)
    monkeypatch.setattr(th.grok, "search_x", fake_grok)
    monkeypatch.setattr(th.perplexity, "search", fake_perplexity)
    monkeypatch.setattr(th.llm, "ask_json", fake_ask_json)

    result = await TrendHunterAgent().discover_topics(limit=3)
    assert "topics" in result
    assert result["topics"][0]["name"] == "AI Receptionist"


# -------------------------------- Scorer ---------------------------------
async def test_scorer_computes_weighted_total_and_keeps(monkeypatch):
    import agents.scorer as sc

    async def fake_ask_json(*args, **kwargs):
        return {"market": 10, "competition": 10, "ease": 10, "scalability": 10, "ai_potential": 10, "profit": 10, "reasoning": "great"}

    monkeypatch.setattr(sc.llm, "ask_json", fake_ask_json)
    result = await ScorerAgent().run(_ctx())
    assert result.data["total"] == 10.0
    assert result.should_discard is False


async def test_scorer_discards_low_score(monkeypatch):
    import agents.scorer as sc

    async def fake_ask_json(*args, **kwargs):
        return {"market": 5, "competition": 5, "ease": 5, "scalability": 5, "ai_potential": 5, "profit": 5}

    monkeypatch.setattr(sc.llm, "ask_json", fake_ask_json)
    result = await ScorerAgent().run(_ctx())
    assert result.data["total"] == 5.0
    assert result.should_discard is True


# ------------------------- Founder Compatibility -------------------------
async def test_founder_compatibility_discards_below_threshold(monkeypatch):
    import agents.founder_compatibility as fc

    async def fake_ask_json(*args, **kwargs):
        return {"score": 30, "available_knowledge_pct": 30, "gap": 70, "time_to_mvp": "?"}

    monkeypatch.setattr(fc.llm, "ask_json", fake_ask_json)
    result = await FounderCompatibilityAgent().run(_ctx())
    assert result.should_discard is True


async def test_founder_compatibility_keeps_high(monkeypatch):
    import agents.founder_compatibility as fc

    async def fake_ask_json(*args, **kwargs):
        return {"score": 85, "available_knowledge_pct": 85, "gap": 15, "time_to_mvp": "2 months"}

    monkeypatch.setattr(fc.llm, "ask_json", fake_ask_json)
    result = await FounderCompatibilityAgent().run(_ctx())
    assert result.should_discard is False


# --------------------------- Project Generator ---------------------------
async def test_project_generator_skips_when_score_below_8(monkeypatch):
    # O pulo por score baixo e comportamento esperado, mas NUNCA pode ficar
    # invisivel: o resultado carrega um marcador explicito com o motivo,
    # para o relatorio nao mostrar "sem dados" como se fosse falha.
    ctx = _ctx()
    ctx.score_data = {"total": 7.5}
    result = await ProjectGeneratorAgent().run(ctx)
    assert result.success is True
    assert result.should_discard is False
    assert result.data["skipped"] is True
    assert result.data["score"] == 7.5
    assert result.data["min_required"] == 8.0
    assert "7.5" in result.data["reason"]


async def test_project_generator_runs_when_score_high(monkeypatch):
    import agents.project_generator as pg

    async def fake_ask_json(*args, **kwargs):
        return {"bmc": {"value_proposition": "x"}, "mvp_features": ["a"], "recommended_stack": ["FastAPI"], "roadmap_90_days": [], "estimated_initial_cost": "$0"}

    monkeypatch.setattr(pg.llm, "ask_json", fake_ask_json)
    ctx = _ctx()
    ctx.score_data = {"total": 9.0}
    result = await ProjectGeneratorAgent().run(ctx)
    assert result.success is True
    assert "bmc" in result.data
