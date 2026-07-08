"""Testes do controle de estado da pipeline (Redis + degradacao graciosa)."""

from core import pipeline_control


class FakeRedis:
    def __init__(self):
        self.store: dict = {}

    def set(self, k, v, nx=False, ex=None):
        if nx and k in self.store:
            return None
        self.store[k] = v
        return True

    def get(self, k):
        return self.store.get(k)

    def delete(self, k):
        self.store.pop(k, None)

    def ping(self):
        return True


class DownRedis:
    def set(self, *a, **k):
        raise ConnectionError("redis down")

    def get(self, *a, **k):
        raise ConnectionError("redis down")

    def delete(self, *a, **k):
        raise ConnectionError("redis down")

    def ping(self, *a, **k):
        raise ConnectionError("redis down")


def _use(monkeypatch, client):
    monkeypatch.setattr(pipeline_control, "_client", lambda: client)


def test_enable_disable_roundtrip(monkeypatch):
    _use(monkeypatch, FakeRedis())
    assert pipeline_control.set_enabled(True) is True
    assert pipeline_control.is_enabled() is True
    assert pipeline_control.set_enabled(False) is True
    assert pipeline_control.is_enabled() is False


def test_run_lock_prevents_double_run(monkeypatch):
    _use(monkeypatch, FakeRedis())
    assert pipeline_control.acquire_run_lock() is True
    assert pipeline_control.acquire_run_lock() is False  # ja travado
    pipeline_control.release_run_lock()
    assert pipeline_control.acquire_run_lock() is True  # liberou


def test_status_roundtrip(monkeypatch):
    _use(monkeypatch, FakeRedis())
    pipeline_control.set_status({"a": 1, "b": "x"})
    assert pipeline_control.get_status() == {"a": 1, "b": "x"}


def test_graceful_degradation_when_redis_down(monkeypatch):
    _use(monkeypatch, DownRedis())
    assert pipeline_control.set_enabled(True) is False       # falha visivel
    assert pipeline_control.is_enabled() is False            # default seguro
    assert pipeline_control.acquire_run_lock() is True       # deixa rodar (is_enabled ja barra)
    assert pipeline_control.get_status() == {}               # default seguro
    assert pipeline_control.redis_available() is False
    pipeline_control.release_run_lock()  # nao pode levantar excecao
