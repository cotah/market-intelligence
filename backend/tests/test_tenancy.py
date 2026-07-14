"""Testes de multi-tenancy (core/tenancy.py + isolamento entre contas).

Contrato:
- Todo endpoint exige o header X-Account-Id (UUID). Sem header ou com valor
  invalido => 400, mesmo com a X-API-Key correta.
- Leituras por id de dado de OUTRA conta => 404 (mesma resposta de "nao
  existe", para nao revelar a existencia de dados alheios).
- pipeline_control usa chaves Redis por conta: ligar a pipeline de uma
  conta nunca liga a de outra.
"""

import uuid

import httpx
import pytest

from core import pipeline_control
from core.config import settings
from core.database import get_session
from main import app
from models import Opportunity
from tests.test_pipeline_control import FakeRedis

READ_KEY = "test-read-key"
RESEARCH_KEY = "test-research-key"

ACC_A = uuid.UUID("00000000-0000-0000-0000-00000000000a")
ACC_B = uuid.UUID("00000000-0000-0000-0000-00000000000b")


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


class FakeSession:
    """Sessao minima: get() devolve sempre o objeto configurado."""

    def __init__(self, get_obj=None) -> None:
        self._get = get_obj

    async def get(self, model, pk):
        return self._get


def _override_session(session) -> None:
    async def fake_session():
        yield session

    app.dependency_overrides[get_session] = fake_session


@pytest.fixture(autouse=True)
def _keys(monkeypatch):
    """Chaves de API validas — o que esta em teste aqui e o tenant, nao a chave."""
    monkeypatch.setattr(settings, "read_api_key", READ_KEY)
    monkeypatch.setattr(settings, "research_api_key", RESEARCH_KEY)
    yield
    app.dependency_overrides.clear()


# ----------------------- Header X-Account-Id obrigatorio -----------------------
async def test_list_opportunities_without_account_header_returns_400():
    async with _client() as c:
        resp = await c.get("/opportunities", headers={"X-API-Key": READ_KEY})
    assert resp.status_code == 400


async def test_list_opportunities_with_invalid_account_header_returns_400():
    async with _client() as c:
        resp = await c.get(
            "/opportunities",
            headers={"X-API-Key": READ_KEY, "X-Account-Id": "nao-e-uuid"},
        )
    assert resp.status_code == 400


async def test_research_list_without_account_header_returns_400():
    async with _client() as c:
        resp = await c.get(
            "/integrations/research/opportunities",
            headers={"X-API-Key": RESEARCH_KEY},
        )
    assert resp.status_code == 400


# ------------------- Isolamento: dado de outra conta => 404 -------------------
async def test_get_opportunity_of_other_account_returns_404():
    opp = Opportunity(id=uuid.uuid4(), account_id=ACC_B)
    _override_session(FakeSession(get_obj=opp))
    async with _client() as c:
        resp = await c.get(
            f"/opportunities/{opp.id}",
            headers={"X-API-Key": READ_KEY, "X-Account-Id": str(ACC_A)},
        )
    assert resp.status_code == 404


async def test_research_get_opportunity_of_other_account_returns_404():
    opp = Opportunity(id=uuid.uuid4(), account_id=ACC_B)
    _override_session(FakeSession(get_obj=opp))
    async with _client() as c:
        resp = await c.get(
            f"/integrations/research/opportunities/{opp.id}",
            headers={"X-API-Key": RESEARCH_KEY, "X-Account-Id": str(ACC_A)},
        )
    assert resp.status_code == 404


# ------------------- pipeline_control: chaves Redis por conta -------------------
def test_pipeline_control_keys_are_isolated_per_account(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(pipeline_control, "_client", lambda: fake)
    assert pipeline_control.set_enabled("a", True) is True
    assert pipeline_control.is_enabled("a") is True
    assert pipeline_control.is_enabled("b") is False  # nao vazou para a outra conta

    pipeline_control.set_status("a", {"topics": 1})
    assert pipeline_control.get_status("b") == {}  # status tambem isolado

    assert pipeline_control.acquire_run_lock("a") is True
    assert pipeline_control.acquire_run_lock("b") is True  # trava e por conta


def test_enabled_accounts_returns_only_enabled(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(pipeline_control, "_client", lambda: fake)
    pipeline_control.set_enabled("a", True)
    pipeline_control.set_enabled("b", False)  # desligada: nao entra na lista
    pipeline_control.set_enabled("c", True)
    assert sorted(pipeline_control.enabled_accounts()) == ["a", "c"]
