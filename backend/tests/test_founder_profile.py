"""Testes do perfil dinamico do fundador.

Cobre o service (seed/get/save/to_dict) com uma sessao fake em memoria
(sem precisar de Postgres) e a ponderacao geografica do Agente 6.
"""

from agents.base import PipelineContext
from agents.founder_compatibility import FounderCompatibilityAgent
from core.founder_profile_service import get_profile, profile_to_dict, save_profile
from models import FounderProfile


class FakeSession:
    """Sessao async minima: simula get/add/flush sem banco real."""

    def __init__(self, existing: FounderProfile | None = None) -> None:
        self._store: dict[int, FounderProfile] = {}
        if existing is not None:
            self._store[existing.id] = existing
        self.added: list[FounderProfile] = []
        self.flushed = 0

    async def get(self, _model, pk):
        return self._store.get(pk)

    def add(self, obj: FounderProfile) -> None:
        self.added.append(obj)
        self._store[obj.id] = obj

    async def flush(self) -> None:
        self.flushed += 1


# -------------------------------- Service --------------------------------
async def test_get_profile_seeds_from_default_when_missing():
    session = FakeSession()
    profile = await get_profile(session)

    assert profile.id == 1
    # Pais derivado do default ("Dublin, Ireland" -> "Ireland").
    assert profile.current_country == "Ireland"
    assert profile in session.added
    assert session.flushed == 1


async def test_get_profile_returns_existing_without_seeding():
    existing = FounderProfile(id=1, name="Henrique", current_country="Brazil")
    session = FakeSession(existing=existing)

    profile = await get_profile(session)

    assert profile is existing
    assert session.added == []


async def test_save_profile_updates_only_provided_fields():
    existing = FounderProfile(
        id=1, name="Old", current_country="Ireland", active_markets=["Ireland"]
    )
    session = FakeSession(existing=existing)

    saved = await save_profile(
        session, {"current_country": "Brazil", "active_markets": ["Brazil", "Portugal"]}
    )

    assert saved.current_country == "Brazil"
    assert saved.active_markets == ["Brazil", "Portugal"]
    assert saved.name == "Old"  # campo nao enviado permanece intacto
    assert session.flushed == 1


async def test_save_profile_creates_when_missing():
    session = FakeSession()

    saved = await save_profile(session, {"name": "New", "current_country": "Spain"})

    assert saved.id == 1
    assert saved.name == "New"
    assert saved in session.added


def test_profile_to_dict_coerces_none_lists_to_empty():
    p = FounderProfile(id=1, name="A", current_country="Ireland")
    p.active_markets = None  # JSONB ainda nao materializado (sem flush no banco)

    d = profile_to_dict(p)

    assert d["name"] == "A"
    assert d["current_country"] == "Ireland"
    assert d["active_markets"] == []


# ----------------------- Ponderacao geografica (Agente 6) -----------------------
def _ctx(topic: str = "AI Receptionist") -> PipelineContext:
    return PipelineContext(topic=topic, opportunity_id="test-id")


async def test_compatibility_injects_country_and_markets_from_profile(monkeypatch):
    import agents.founder_compatibility as fc

    captured: dict[str, str] = {}

    async def fake_ask_json(prompt, *args, **kwargs):
        captured["prompt"] = prompt
        return {"score": 80, "geographic_fit": "high"}

    monkeypatch.setattr(fc.llm, "ask_json", fake_ask_json)

    ctx = _ctx()
    ctx.founder_profile = {
        "current_country": "Brazil",
        "active_markets": ["Brazil", "Portugal"],
    }

    result = await fc.FounderCompatibilityAgent().run(ctx)

    prompt = captured["prompt"]
    assert "GEOGRAPHIC WEIGHTING" in prompt
    assert "based in: Brazil" in prompt
    assert "Brazil, Portugal" in prompt
    # O fit geografico retornado pelo LLM eh preservado nos dados.
    assert result.data["geographic_fit"] == "high"
    assert result.should_discard is False


async def test_compatibility_falls_back_to_default_profile(monkeypatch):
    import agents.founder_compatibility as fc

    captured: dict[str, str] = {}

    async def fake_ask_json(prompt, *args, **kwargs):
        captured["prompt"] = prompt
        return {"score": 75}

    monkeypatch.setattr(fc.llm, "ask_json", fake_ask_json)

    ctx = _ctx()  # founder_profile = None -> usa default_profile_dict()

    await fc.FounderCompatibilityAgent().run(ctx)

    # Default deriva o pais "Ireland" do perfil hardcoded.
    assert "based in: Ireland" in captured["prompt"]
