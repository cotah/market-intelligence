"""Testes do perfil dinamico do fundador.

Cobre o service (seed/get/save/to_dict) com uma sessao fake em memoria
(sem precisar de Postgres) e a ponderacao geografica do Agente 6.
"""

import uuid

from agents.base import PipelineContext
from core.founder_profile_service import get_profile, profile_to_dict, save_profile
from models import FounderProfile

# Conta usada nos testes do service (1 perfil POR conta).
ACC = uuid.UUID("00000000-0000-0000-0000-000000000001")


class FakeSession:
    """Sessao async minima: simula get/add/flush sem banco real."""

    def __init__(self, existing: FounderProfile | None = None) -> None:
        self._store: dict[uuid.UUID, FounderProfile] = {}
        if existing is not None:
            self._store[existing.account_id] = existing
        self.added: list[FounderProfile] = []
        self.flushed = 0

    async def get(self, _model, pk):
        return self._store.get(pk)

    def add(self, obj: FounderProfile) -> None:
        self.added.append(obj)
        self._store[obj.account_id] = obj

    async def flush(self) -> None:
        self.flushed += 1


# -------------------------------- Service --------------------------------
async def test_get_profile_seeds_from_default_when_missing():
    session = FakeSession()
    profile = await get_profile(session, ACC)

    assert profile.account_id == ACC
    # Pais derivado do default ("Dublin, Ireland" -> "Ireland").
    assert profile.current_country == "Ireland"
    assert profile in session.added
    assert session.flushed == 1


async def test_get_profile_returns_existing_without_seeding():
    existing = FounderProfile(account_id=ACC, name="Henrique", current_country="Brazil")
    session = FakeSession(existing=existing)

    profile = await get_profile(session, ACC)

    assert profile is existing
    assert session.added == []


async def test_save_profile_updates_only_provided_fields():
    existing = FounderProfile(
        account_id=ACC, name="Old", current_country="Ireland", active_markets=["Ireland"]
    )
    session = FakeSession(existing=existing)

    saved = await save_profile(
        session, ACC, {"current_country": "Brazil", "active_markets": ["Brazil", "Portugal"]}
    )

    assert saved.current_country == "Brazil"
    assert saved.active_markets == ["Brazil", "Portugal"]
    assert saved.name == "Old"  # campo nao enviado permanece intacto
    assert session.flushed == 1


async def test_save_profile_creates_when_missing():
    session = FakeSession()

    saved = await save_profile(session, ACC, {"name": "New", "current_country": "Spain"})

    assert saved.account_id == ACC
    assert saved.name == "New"
    assert saved in session.added


def test_profile_to_dict_coerces_none_lists_to_empty():
    p = FounderProfile(account_id=ACC, name="A", current_country="Ireland")
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


async def test_compatibility_injects_separated_tools(monkeypatch):
    import agents.founder_compatibility as fc

    captured: dict[str, str] = {}

    async def fake_ask_json(prompt, *args, **kwargs):
        captured["prompt"] = prompt
        return {"score": 70}

    monkeypatch.setattr(fc.llm, "ask_json", fake_ask_json)

    ctx = _ctx()
    ctx.founder_profile = {
        "ai_tools": ["Claude Code"],
        "software_tools": ["Vercel"],
        "hardware_tools": ["NFC Reader"],
    }

    await fc.FounderCompatibilityAgent().run(ctx)

    prompt = captured["prompt"]
    assert "FOUNDER TOOLING" in prompt
    assert "Claude Code" in prompt
    assert "Vercel" in prompt
    assert "NFC Reader" in prompt


def test_default_profile_has_separated_tools():
    from core.founder_profile import default_profile_dict

    d = default_profile_dict()

    assert d["ai_tools"]  # nao vazio
    assert "software_tools" in d
    assert "hardware_tools" in d
    # O campo legado nao faz mais parte do perfil dinamico.
    assert "tools_available" not in d


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
