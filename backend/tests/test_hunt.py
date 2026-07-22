"""Testes do cacador controlado pelo cliente (hunt_settings + /hunt/* + worker)."""

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from core import hunt_service, pipeline_control
from core.config import settings
from core.database import get_session
from main import app
from models import HuntSettings
from workers import pipeline_worker

READ_KEY = "test-read-key"
CONTROL_KEY = "test-control-key"
ACC = "00000000-0000-0000-0000-000000000001"
READ_HEAD = {"X-API-Key": READ_KEY, "X-Account-Id": ACC}
CONTROL_HEAD = {"X-API-Key": CONTROL_KEY, "X-Account-Id": ACC}


# ------------------------- hunt_service (logica pura) -------------------------
def test_next_run_none_when_manual_or_disabled():
    assert hunt_service.compute_next_run_at(True, "manual") is None
    assert hunt_service.compute_next_run_at(False, "daily") is None
    assert hunt_service.compute_next_run_at(True, "invalida") is None


def test_next_run_adds_frequency_delta():
    base = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)
    assert hunt_service.compute_next_run_at(True, "daily", base) == base + timedelta(days=1)
    assert hunt_service.compute_next_run_at(True, "weekly", base) == base + timedelta(weeks=1)
    assert hunt_service.compute_next_run_at(True, "monthly", base) == base + timedelta(days=30)


# ------------------------------- Rotas /hunt --------------------------------
class FakeSession:
    def __init__(self, get_obj=None):
        self._get = get_obj
        self.added: list = []

    async def get(self, model, ident):
        return self._get

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        return None


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def _override(session):
    async def fake_session():
        yield session

    app.dependency_overrides[get_session] = fake_session


@pytest.fixture(autouse=True)
def _keys(monkeypatch):
    monkeypatch.setattr(settings, "read_api_key", READ_KEY)
    monkeypatch.setattr(settings, "control_api_key", CONTROL_KEY)
    yield
    app.dependency_overrides.clear()


async def test_get_hunt_settings_seeds_default_off():
    """GET sem linha existente: cria o default DESLIGADO (opt-in)."""
    fake = FakeSession(get_obj=None)
    _override(fake)
    async with _client() as c:
        resp = await c.get("/hunt/settings", headers=READ_HEAD)
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is False
    assert body["frequency"] == "manual"
    assert body["topic"] == ""
    assert body["next_run_at"] is None
    assert len(fake.added) == 1  # semeou a linha default


async def test_get_hunt_settings_requires_account_header():
    _override(FakeSession())
    async with _client() as c:
        resp = await c.get("/hunt/settings", headers={"X-API-Key": READ_KEY})
    assert resp.status_code == 400


async def test_put_hunt_settings_enables_and_schedules_first_run():
    """Ligar daily pela 1a vez: next_run_at = agora (roda na proxima varredura)."""
    _override(FakeSession(get_obj=None))
    async with _client() as c:
        resp = await c.put(
            "/hunt/settings",
            headers=CONTROL_HEAD,
            json={"enabled": True, "frequency": "daily", "topic": "manicure em Dublin"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is True
    assert body["frequency"] == "daily"
    assert body["topic"] == "manicure em Dublin"
    assert body["next_run_at"] is not None


async def test_put_hunt_settings_manual_clears_schedule():
    row = HuntSettings(
        account_id=uuid.UUID(ACC),
        enabled=True,
        frequency="daily",
        topic="x",
        next_run_at=datetime.now(UTC),
    )
    _override(FakeSession(get_obj=row))
    async with _client() as c:
        resp = await c.put(
            "/hunt/settings",
            headers=CONTROL_HEAD,
            json={"enabled": True, "frequency": "manual", "topic": "x"},
        )
    assert resp.status_code == 200
    assert resp.json()["next_run_at"] is None


async def test_put_hunt_settings_rejects_invalid_frequency():
    _override(FakeSession())
    async with _client() as c:
        resp = await c.put(
            "/hunt/settings",
            headers=CONTROL_HEAD,
            json={"enabled": True, "frequency": "hourly", "topic": ""},
        )
    assert resp.status_code == 422


async def test_post_hunt_run_returns_run_id(monkeypatch):
    class FakeTask:
        id = "task-123"

    monkeypatch.setattr(
        pipeline_worker.run_hunt_task, "delay", lambda **kwargs: FakeTask()
    )
    async with _client() as c:
        resp = await c.post("/hunt/run", headers=CONTROL_HEAD)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "queued"
    assert body["run_id"] == "task-123"


# ------------------------------ Worker / Beat --------------------------------
def _fake_asyncio_run_sequence(results):
    """asyncio.run fake que devolve os resultados na ordem das chamadas."""
    remaining = list(results)

    def run(coro):
        coro.close()
        return remaining.pop(0)

    return run


def test_hunt_task_skips_when_already_running(monkeypatch):
    monkeypatch.setattr(pipeline_control, "acquire_run_lock", lambda account_id: False)
    ran = {"n": 0}
    monkeypatch.setattr(
        pipeline_worker.asyncio, "run", lambda c: (c.close(), ran.__setitem__("n", 1))
    )
    assert pipeline_worker.run_hunt_task.apply(kwargs={"account_id": ACC}).get() is None
    assert ran["n"] == 0


def test_hunt_task_runs_records_and_releases(monkeypatch):
    monkeypatch.setattr(pipeline_control, "acquire_run_lock", lambda account_id: True)
    released = {"n": 0}
    monkeypatch.setattr(
        pipeline_control,
        "release_run_lock",
        lambda account_id: released.__setitem__("n", released["n"] + 1),
    )
    saved = {}
    monkeypatch.setattr(pipeline_control, "set_status", lambda account_id, d: saved.update(d))

    summary = {"topics": 2, "completed": 1, "opportunity_ids": ["x"]}
    # 3 chamadas de asyncio.run: start (run_pk, topic) -> pipeline -> finish.
    monkeypatch.setattr(
        pipeline_worker.asyncio,
        "run",
        _fake_asyncio_run_sequence([(uuid.uuid4(), "manicure em Dublin"), summary, None]),
    )
    result = pipeline_worker.run_hunt_task.apply(
        kwargs={"account_id": ACC, "trigger": "scheduled"}
    ).get()
    assert result == summary
    assert released["n"] == 1
    assert saved["topic"] == "manicure em Dublin"
    assert saved["trigger"] == "hunt_scheduled"


def test_hunt_dispatch_enqueues_due_accounts(monkeypatch):
    monkeypatch.setattr(
        pipeline_worker.asyncio, "run", _fake_asyncio_run_sequence([["acc-a", "acc-b"]])
    )
    dispatched: list[tuple] = []
    monkeypatch.setattr(
        pipeline_worker.run_hunt_task,
        "delay",
        lambda **kwargs: dispatched.append((kwargs["account_id"], kwargs["trigger"])),
    )
    result = pipeline_worker.hunt_scheduler_dispatch.apply().get()
    assert result == {"dispatched_accounts": 2}
    assert dispatched == [("acc-a", "scheduled"), ("acc-b", "scheduled")]


def test_hunt_dispatch_survives_db_timeout(monkeypatch):
    """Soluco do banco (TimeoutError no connect) NAO pode derrubar o tick do Beat.

    Reproduz o erro visto no Sentry (trace 9d98625f9da2): o dispatch loga,
    reporta como handled e devolve 0 contas — o proximo tick re-tenta.
    """

    def _db_down(coro):
        coro.close()
        raise TimeoutError("connect to postgres.railway.internal:5432 timed out")

    monkeypatch.setattr(pipeline_worker.asyncio, "run", _db_down)
    dispatched: list = []
    monkeypatch.setattr(
        pipeline_worker.run_hunt_task, "delay", lambda **kwargs: dispatched.append(kwargs)
    )
    captured: list = []
    monkeypatch.setattr(
        pipeline_worker.sentry_sdk, "capture_exception", lambda e: captured.append(e)
    )

    result = pipeline_worker.hunt_scheduler_dispatch.apply()
    assert result.successful()  # a task nao pode explodir
    assert result.get() == {"dispatched_accounts": 0, "error": "TimeoutError"}
    assert dispatched == []  # nada enfileirado num tick com banco fora
    assert len(captured) == 1  # erro foi pro Sentry como handled
