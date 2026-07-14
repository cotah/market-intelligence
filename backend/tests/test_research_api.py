"""Testes do endpoint da ponte Research Agent (n8n) -> busca.

Sem rede e sem banco real: a sessao e substituida via dependency_overrides
e a chave de API e injetada via monkeypatch em settings.

Contrato de status codes (nao mascarar erro como sucesso):
  200 sucesso | 401 sem chave | 403 chave errada | 404 nao encontrado
  422 payload invalido | 503 endpoint nao configurado
"""

import uuid
from datetime import datetime

import httpx
import pytest

from core.config import settings
from core.database import get_session
from main import app
from models import Opportunity, OpportunityStatus

TEST_KEY = "test-research-key"
ACC = uuid.UUID("00000000-0000-0000-0000-000000000001")
HEADERS = {"X-API-Key": TEST_KEY, "X-Account-Id": str(ACC)}
URL = "/integrations/research/opportunities"


def _client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _opportunity(**overrides) -> Opportunity:
    """Opportunity completa o suficiente para serializar em OpportunityOut."""
    now = datetime(2026, 6, 26, 12, 0, 0)
    defaults = dict(
        id=uuid.uuid4(),
        account_id=ACC,
        title="Vertical AI SaaS",
        summary="",
        topic_origin="Vertical AI SaaS",
        source="trend_hunter",
        status=OpportunityStatus.COMPLETED,
        discard_reason=None,
        discarded_by=None,
        failed_agents=None,
        trend_data={"name": "Vertical AI SaaS"},
        problem_data={"pain_phrases": ["I hate generic tools"]},
        competitor_data=None,
        market_data=None,
        ai_opportunity_data=None,
        compatibility_data=None,
        monetization_data=None,
        score_data={"total": 7.0},
        project_plan=None,
        devils_advocate_data=None,
        score_total=7.0,
        created_at=now,
        updated_at=now,
    )
    defaults.update(overrides)
    return Opportunity(**defaults)


class FakeResult:
    def __init__(self, items: list) -> None:
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items


class FakeSession:
    """Sessao minima: execute() lista, get() busca por id."""

    def __init__(self, items: list | None = None) -> None:
        self.items = items or []

    async def execute(self, stmt):
        return FakeResult(self.items)

    async def get(self, model, pk):
        for item in self.items:
            if item.id == pk:
                return item
        return None


def _override_session(items: list | None = None) -> None:
    async def fake_session():
        yield FakeSession(items)

    app.dependency_overrides[get_session] = fake_session


@pytest.fixture(autouse=True)
def configured_key(monkeypatch):
    """Chave dedicada configurada por padrao; testes especificos limpam."""
    monkeypatch.setattr(settings, "research_api_key", TEST_KEY)
    yield
    app.dependency_overrides.clear()


# ------------------------------ Autenticacao ------------------------------
async def test_returns_503_when_key_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "research_api_key", "")
    async with _client() as client:
        resp = await client.get(URL, headers=HEADERS)
    assert resp.status_code == 503


async def test_returns_401_without_api_key_header():
    async with _client() as client:
        resp = await client.get(URL)
    assert resp.status_code == 401


async def test_returns_403_with_wrong_api_key():
    async with _client() as client:
        resp = await client.get(URL, headers={"X-API-Key": "wrong-key"})
    assert resp.status_code == 403


# -------------------------------- Modo mock --------------------------------
async def test_mock_mode_returns_sample_payload_without_db():
    # Sem override de sessao: se o mock tocar o banco, o teste quebra.
    app.dependency_overrides.pop(get_session, None)
    async with _client() as client:
        resp = await client.get(URL, params={"mock": "true"}, headers=HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["mock"] is True
    assert body["count"] == len(body["opportunities"]) > 0
    # Estrutura reaproveita os campos que os agentes ja produzem.
    first = body["opportunities"][0]
    for field in ("id", "title", "status", "score_total", "score_data", "devils_advocate_data"):
        assert field in first


# -------------------------------- Modo real --------------------------------
async def test_lists_opportunities_from_db():
    opp = _opportunity()
    _override_session([opp])
    async with _client() as client:
        resp = await client.get(URL, headers=HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["mock"] is False
    assert body["count"] == 1
    assert body["opportunities"][0]["id"] == str(opp.id)
    assert body["opportunities"][0]["score_total"] == 7.0


async def test_get_by_id_returns_404_when_missing():
    _override_session([])
    async with _client() as client:
        resp = await client.get(f"{URL}/{uuid.uuid4()}", headers=HEADERS)
    assert resp.status_code == 404


async def test_get_by_id_returns_opportunity():
    opp = _opportunity()
    _override_session([opp])
    async with _client() as client:
        resp = await client.get(f"{URL}/{opp.id}", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["id"] == str(opp.id)


# ------------------------------- Validacao --------------------------------
async def test_rejects_invalid_score_min_with_422():
    async with _client() as client:
        resp = await client.get(URL, params={"score_min": 15}, headers=HEADERS)
    assert resp.status_code == 422


async def test_rejects_invalid_status_with_422():
    async with _client() as client:
        resp = await client.get(URL, params={"status": "banana"}, headers=HEADERS)
    assert resp.status_code == 422
