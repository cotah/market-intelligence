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
    """Mocka todas as fontes do Problem Hunter (Perplexity, Reddit,
    Instagram, TikTok, App Reviews). Retorna um dict `calls` que registra
    os argumentos passados a cada fonte, para os testes inspecionarem."""
    import agents.problem_hunter as ph

    calls: dict = {}

    async def fake_perplexity(query, focus="internet"):
        return "Users complain a lot about this."

    async def fake_reddit(subreddit, query):
        return [{"title": "I hate X", "body": "...", "upvotes": 10, "subreddit": "all", "is_mock": True}]

    async def fake_instagram(hashtag):
        calls["instagram_hashtag"] = hashtag
        return [{"caption": "so annoying #pain", "likes": 10, "hashtag": hashtag, "is_mock": True}]

    async def fake_tiktok(hashtag):
        calls["tiktok_hashtag"] = hashtag
        return [{"description": "this is broken", "likes": 99, "hashtag": hashtag, "is_mock": True}]

    async def fake_find_app(topic):
        calls["find_app_topic"] = topic
        return {"app_id": "123456", "name": "Some App"}

    async def fake_get_reviews(app_id):
        calls["reviews_app_id"] = app_id
        return [{"title": "Buggy", "body": "It crashes", "rating": 2, "is_mock": True}]

    monkeypatch.setattr(ph.perplexity, "search", fake_perplexity)
    monkeypatch.setattr(ph.reddit, "search_reddit", fake_reddit)
    monkeypatch.setattr(ph.instagram, "search_hashtag", fake_instagram)
    monkeypatch.setattr(ph.tiktok, "search_hashtag", fake_tiktok)
    monkeypatch.setattr(ph.app_reviews, "find_app", fake_find_app)
    monkeypatch.setattr(ph.app_reviews, "get_reviews", fake_get_reviews)
    return calls


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


async def test_problem_hunter_normalizes_topic_into_hashtag(monkeypatch, patch_problem_sources):
    """Hashtag para Instagram/TikTok = topico lowercase e sem espacos."""
    import agents.problem_hunter as ph

    async def fake_ask_json(*args, **kwargs):
        return {"pain_phrases": ["a", "b", "c", "d"], "problems": [], "sources": [], "has_real_pain": True}

    monkeypatch.setattr(ph.llm, "ask_json", fake_ask_json)

    await ProblemHunterAgent().run(_ctx("AI Receptionist"))

    assert patch_problem_sources["instagram_hashtag"] == "aireceptionist"
    assert patch_problem_sources["tiktok_hashtag"] == "aireceptionist"
    assert patch_problem_sources["reviews_app_id"] == "123456"


async def test_problem_hunter_skips_app_reviews_when_no_app_found(monkeypatch, patch_problem_sources):
    """Sem app na App Store para o topico -> pula a fonte, nao quebra."""
    import agents.problem_hunter as ph

    async def fake_find_app(topic):
        return None

    async def fake_ask_json(*args, **kwargs):
        return {"pain_phrases": ["a", "b", "c", "d"], "problems": [], "sources": [], "has_real_pain": True}

    monkeypatch.setattr(ph.app_reviews, "find_app", fake_find_app)
    monkeypatch.setattr(ph.llm, "ask_json", fake_ask_json)

    result = await ProblemHunterAgent().run(_ctx())

    assert result.success is True
    assert "reviews_app_id" not in patch_problem_sources


async def test_problem_hunter_survives_new_sources_failing(monkeypatch, patch_problem_sources):
    """Instagram/TikTok/App Reviews explodindo nao derruba o agente."""
    import agents.problem_hunter as ph

    async def boom(*args, **kwargs):
        raise RuntimeError("source down")

    async def fake_ask_json(*args, **kwargs):
        return {"pain_phrases": ["a", "b", "c", "d"], "problems": [], "sources": [], "has_real_pain": True}

    monkeypatch.setattr(ph.instagram, "search_hashtag", boom)
    monkeypatch.setattr(ph.tiktok, "search_hashtag", boom)
    monkeypatch.setattr(ph.app_reviews, "find_app", boom)
    monkeypatch.setattr(ph.llm, "ask_json", fake_ask_json)

    result = await ProblemHunterAgent().run(_ctx())

    assert result.success is True
    assert result.should_discard is False


def test_problem_hunter_formats_new_evidence_blocks():
    """Instagram, TikTok e App Reviews viram blocos proprios na evidencia."""
    evidence = ProblemHunterAgent._format_evidence(
        perplexity_text="",
        reddit_posts=[],
        instagram_posts=[{"caption": "ugh, so hard", "likes": 42, "hashtag": "x", "is_mock": False}],
        tiktok_posts=[{"description": "nothing works", "likes": 7, "hashtag": "x", "is_mock": False}],
        app_name="Invoice Maker Pro",
        reviews=[{"title": "Crashes", "body": "loses my data", "rating": 1, "is_mock": False}],
    )

    assert "[Instagram]" in evidence
    assert "ugh, so hard" in evidence
    assert "[TikTok]" in evidence
    assert "nothing works" in evidence
    assert "[App Store reviews - Invoice Maker Pro]" in evidence
    assert "loses my data" in evidence


# ------------------------------ Trend Hunter ------------------------------
@pytest.fixture
def patch_trend_sources(monkeypatch):
    """Mocka todas as fontes do Trend Hunter. Google Trends comeca
    retornando None (mantem estimativa do LLM); os testes sobrescrevem."""
    import agents.trend_hunter as th

    async def fake_serper(query, num_results=10):
        return [{"title": "AI tools", "link": "x", "snippet": "growing fast"}]

    async def fake_grok(query):
        return "People love AI receptionists."

    async def fake_perplexity(query, focus="internet"):
        return "Product Hunt is full of AI scheduling tools."

    async def fake_hackernews(limit=10):
        return [{"title": "Show HN: AI receptionist", "score": 512, "url": "http://x", "num_comments": 231, "is_mock": False}]

    async def fake_trend_score(keyword):
        return None

    async def fake_ask_json(*args, **kwargs):
        return {"topics": [{"name": "AI Receptionist", "growth_signal": "medium", "sources": ["X/Twitter"], "evidence": "...", "search_volume_trend": "unknown"}]}

    monkeypatch.setattr(th.serper, "google_search", fake_serper)
    monkeypatch.setattr(th.grok, "search_x", fake_grok)
    monkeypatch.setattr(th.perplexity, "search", fake_perplexity)
    monkeypatch.setattr(th.hackernews, "get_top_stories", fake_hackernews)
    monkeypatch.setattr(th.google_trends, "get_trend_score", fake_trend_score)
    monkeypatch.setattr(th.llm, "ask_json", fake_ask_json)


async def test_trend_hunter_discover_topics(patch_trend_sources):
    result = await TrendHunterAgent().discover_topics(limit=3)
    assert "topics" in result
    assert result["topics"][0]["name"] == "AI Receptionist"


async def test_trend_hunter_keeps_llm_estimate_when_trends_unavailable(patch_trend_sources):
    """get_trend_score -> None mantem o achismo do LLM intacto."""
    result = await TrendHunterAgent().discover_topics(limit=3)

    topic = result["topics"][0]
    assert topic["growth_signal"] == "medium"
    assert topic["search_volume_trend"] == "unknown"
    assert "Google Trends" not in topic["sources"]


@pytest.mark.parametrize(
    ("direction", "expected_trend", "expected_signal"),
    [
        ("rising", "increasing", "high"),
        ("stable", "stable", "medium"),
        ("falling", "decreasing", "low"),
    ],
)
async def test_trend_hunter_google_trends_overrides_llm_estimate(
    monkeypatch, patch_trend_sources, direction, expected_trend, expected_signal
):
    """Dado real do Google Trends sobrescreve a estimativa do LLM."""
    import agents.trend_hunter as th

    async def fake_trend_score(keyword):
        return {
            "keyword": keyword,
            "interest_over_time": [{"date": "2026-06-01", "value": 50}],
            "trend_direction": direction,
            "is_mock": False,
        }

    monkeypatch.setattr(th.google_trends, "get_trend_score", fake_trend_score)

    result = await TrendHunterAgent().discover_topics(limit=3)

    topic = result["topics"][0]
    assert topic["search_volume_trend"] == expected_trend
    assert topic["growth_signal"] == expected_signal
    assert "Google Trends" in topic["sources"]


def test_trend_hunter_formats_hackernews_block():
    """Stories do HN viram bloco proprio nas fontes do LLM."""
    sources = TrendHunterAgent._format_sources(
        serper_results=[],
        grok_text="",
        ph_text="",
        hn_stories=[{"title": "Show HN: AI receptionist", "score": 512, "url": "http://x", "num_comments": 231, "is_mock": False}],
    )

    assert "[Hacker News - top stories]" in sources
    assert "Show HN: AI receptionist" in sources
    assert "512" in sources


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
