"""Testes de autenticacao dos endpoints de CONTROLE.

Endpoints que gastam creditos de LLM ou alteram estado exigem a chave
CONTROL_API_KEY (header X-API-Key), no mesmo padrao da Research API:

  200 sucesso | 401 sem chave | 403 chave errada | 503 nao configurado

Protegidos: POST /pipeline/start, POST /pipeline/stop,
POST /pipeline/run-once, PUT /founder-profile, POST /reports/daily/generate.

Leituras (GET) agora exigem READ_API_KEY (achado I-1 da auditoria);
ver tests/test_read_auth.py para o contrato completo.
"""

import httpx
import pytest

from core import pipeline_control
from core.config import settings
from core.database import get_session
from core.founder_profile import default_profile_dict
from main import app

TEST_KEY = "test-control-key"
ACC = "00000000-0000-0000-0000-000000000001"
HEADERS = {"X-API-Key": TEST_KEY, "X-Account-Id": ACC}

TEST_READ_KEY = "test-read-key"
READ_HEADERS = {"X-API-Key": TEST_READ_KEY, "X-Account-Id": ACC}

# (metodo, caminho) de todos os endpoints protegidos.
PROTECTED = [
    ("POST", "/pipeline/start"),
    ("POST", "/pipeline/stop"),
    ("POST", "/pipeline/run-once"),
    ("PUT", "/founder-profile"),
    ("POST", "/reports/daily/generate"),
]


def _client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture(autouse=True)
def configured_key(monkeypatch):
    """Chave de controle configurada por padrao; testes especificos limpam."""
    monkeypatch.setattr(settings, "control_api_key", TEST_KEY)
    monkeypatch.setattr(settings, "read_api_key", TEST_READ_KEY)
    yield
    app.dependency_overrides.clear()


# ---------------------- Rejeicoes (todos os protegidos) ----------------------
@pytest.mark.parametrize("method,path", PROTECTED)
async def test_returns_503_when_key_not_configured(monkeypatch, method, path):
    monkeypatch.setattr(settings, "control_api_key", "")
    async with _client() as client:
        resp = await client.request(method, path, headers=HEADERS)
    assert resp.status_code == 503


@pytest.mark.parametrize("method,path", PROTECTED)
async def test_returns_401_without_api_key_header(method, path):
    async with _client() as client:
        resp = await client.request(method, path)
    assert resp.status_code == 401


@pytest.mark.parametrize("method,path", PROTECTED)
async def test_returns_403_with_wrong_api_key(method, path):
    async with _client() as client:
        resp = await client.request(method, path, headers={"X-API-Key": "wrong-key"})
    assert resp.status_code == 403


# ------------------------ Sucesso com a chave certa ------------------------
async def test_stop_pipeline_succeeds_with_valid_key(monkeypatch):
    monkeypatch.setattr(pipeline_control, "set_enabled", lambda account_id, value: True)
    async with _client() as client:
        resp = await client.post("/pipeline/stop", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


async def test_put_founder_profile_succeeds_with_valid_key(monkeypatch):
    async def fake_save(session, account_id, data):
        return data

    def fake_to_dict(profile):
        return profile

    import api.routes as routes

    monkeypatch.setattr(routes, "save_profile", fake_save)
    monkeypatch.setattr(routes, "profile_to_dict", fake_to_dict)

    async def fake_session():
        yield None

    app.dependency_overrides[get_session] = fake_session

    async with _client() as client:
        resp = await client.put("/founder-profile", headers=HEADERS, json=default_profile_dict())
    assert resp.status_code == 200
    assert resp.json()["name"] == "Henrique"


# --------------- GETs agora exigem READ_API_KEY (achado I-1) ----------------
async def test_get_founder_profile_requires_read_key(monkeypatch):
    import api.routes as routes

    async def fake_get(session, account_id):
        return default_profile_dict()

    monkeypatch.setattr(routes, "get_profile", fake_get)
    monkeypatch.setattr(routes, "profile_to_dict", lambda p: p)

    async def fake_session():
        yield None

    app.dependency_overrides[get_session] = fake_session

    # Sem chave => 401 (achado I-1: leitura nao e mais publica).
    async with _client() as client:
        resp = await client.get("/founder-profile")
    assert resp.status_code == 401
    # Com a READ_API_KEY correta => 200.
    async with _client() as client:
        resp = await client.get("/founder-profile", headers=READ_HEADERS)
    assert resp.status_code == 200


async def test_pipeline_status_requires_read_key(monkeypatch):
    monkeypatch.setattr(pipeline_control, "is_enabled", lambda account_id: False)
    monkeypatch.setattr(pipeline_control, "redis_available", lambda: False)
    monkeypatch.setattr(pipeline_control, "get_status", lambda account_id: {})
    # Sem chave => 401.
    async with _client() as client:
        resp = await client.get("/pipeline/status")
    assert resp.status_code == 401
    # Com a READ_API_KEY correta => 200.
    async with _client() as client:
        resp = await client.get("/pipeline/status", headers=READ_HEADERS)
    assert resp.status_code == 200
