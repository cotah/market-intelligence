"""Testes do endpoint POST /opportunities/from-idea (modo Ideia)."""

import httpx
import pytest

from core.config import settings
from main import app

TEST_KEY = "test-control-key"
ACC = "00000000-0000-0000-0000-000000000001"
HEADERS = {"X-API-Key": TEST_KEY, "X-Account-Id": ACC}
BODY = {"name": "Coleira GPS", "description": "rastreador pet"}


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest.fixture(autouse=True)
def _configured(monkeypatch):
    monkeypatch.setattr(settings, "control_api_key", TEST_KEY)
    yield
    app.dependency_overrides.clear()


async def test_from_idea_503_when_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "control_api_key", "")
    async with _client() as c:
        r = await c.post("/opportunities/from-idea", json=BODY, headers=HEADERS)
    assert r.status_code == 503


async def test_from_idea_401_without_key():
    async with _client() as c:
        r = await c.post("/opportunities/from-idea", json=BODY)
    assert r.status_code == 401


async def test_from_idea_403_with_wrong_key():
    async with _client() as c:
        r = await c.post("/opportunities/from-idea", json=BODY, headers={"X-API-Key": "wrong"})
    assert r.status_code == 403


async def test_from_idea_422_on_invalid_body():
    async with _client() as c:
        r = await c.post("/opportunities/from-idea", json={"name": ""}, headers=HEADERS)
    assert r.status_code == 422


async def test_from_idea_enqueues_with_valid_key(monkeypatch):
    import workers.pipeline_worker as w

    class FakeTask:
        id = "task-123"

    monkeypatch.setattr(w.run_for_idea_task, "delay", lambda idea, account_id: FakeTask())
    async with _client() as c:
        r = await c.post("/opportunities/from-idea", json=BODY, headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["task_id"] == "task-123"
