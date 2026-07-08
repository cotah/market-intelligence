"""Testes de autenticacao dos endpoints de LEITURA.

Apos o fechamento do backend (achado I-1 da auditoria), os GET de dados
exigem a chave READ_API_KEY (header X-API-Key), no mesmo padrao dos
endpoints de controle:

  200 sucesso | 401 sem chave | 403 chave errada | 503 nao configurado

Protegidos: GET /opportunities, GET /opportunities/{id}, GET /founder-profile,
GET /reports/daily, GET /reports/daily/latest, GET /pipeline/status.
/health permanece publico.
"""

import httpx
import pytest

from core.config import settings
from main import app

TEST_READ_KEY = "test-read-key"

PROTECTED_GETS = [
    "/opportunities",
    "/opportunities/00000000-0000-0000-0000-000000000000",
    "/founder-profile",
    "/reports/daily",
    "/reports/daily/latest",
    "/pipeline/status",
]


def _client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture(autouse=True)
def configured_key(monkeypatch):
    monkeypatch.setattr(settings, "read_api_key", TEST_READ_KEY)
    yield
    app.dependency_overrides.clear()


@pytest.mark.parametrize("path", PROTECTED_GETS)
async def test_returns_503_when_read_key_not_configured(monkeypatch, path):
    monkeypatch.setattr(settings, "read_api_key", "")
    async with _client() as client:
        resp = await client.get(path, headers={"X-API-Key": TEST_READ_KEY})
    assert resp.status_code == 503


@pytest.mark.parametrize("path", PROTECTED_GETS)
async def test_returns_401_without_key(path):
    async with _client() as client:
        resp = await client.get(path)
    assert resp.status_code == 401


@pytest.mark.parametrize("path", PROTECTED_GETS)
async def test_returns_403_with_wrong_key(path):
    async with _client() as client:
        resp = await client.get(path, headers={"X-API-Key": "wrong"})
    assert resp.status_code == 403


async def test_health_stays_public():
    async with _client() as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
