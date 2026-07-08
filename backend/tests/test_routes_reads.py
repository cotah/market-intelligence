"""Testes dos handlers de LEITURA (corpo dos endpoints, com a chave)."""

import uuid

import httpx
import pytest

from core.config import settings
from core.database import get_session
from main import app

READ_KEY = "test-read-key"
HEAD = {"X-API-Key": READ_KEY}


class FakeResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None


class FakeSession:
    def __init__(self, items=None, get_obj="unset"):
        self._items = items or []
        self._get = get_obj

    async def execute(self, stmt):
        return FakeResult(self._items)

    async def get(self, model, ident):
        return None if self._get == "unset" else self._get


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


def _override(session):
    async def fake_session():
        yield session

    app.dependency_overrides[get_session] = fake_session


@pytest.fixture(autouse=True)
def _read_key(monkeypatch):
    monkeypatch.setattr(settings, "read_api_key", READ_KEY)
    yield
    app.dependency_overrides.clear()


async def test_list_opportunities_empty():
    _override(FakeSession(items=[]))
    async with _client() as c:
        resp = await c.get("/opportunities", headers=HEAD)
    assert resp.status_code == 200
    assert resp.json() == []


async def test_get_opportunity_not_found():
    _override(FakeSession(get_obj=None))
    async with _client() as c:
        resp = await c.get(f"/opportunities/{uuid.uuid4()}", headers=HEAD)
    assert resp.status_code == 404


async def test_latest_daily_report_not_found():
    _override(FakeSession(items=[]))
    async with _client() as c:
        resp = await c.get("/reports/daily/latest", headers=HEAD)
    assert resp.status_code == 404
