"""Testes da inicializacao do Sentry (observabilidade)."""

from core import observability
from core.config import settings


def test_sentry_noop_without_dsn(monkeypatch):
    monkeypatch.setattr(settings, "sentry_dsn", "")
    monkeypatch.setattr(observability, "_initialized", False)
    assert observability.init_sentry() is False


def test_sentry_enabled_with_dsn(monkeypatch):
    captured: dict = {}

    def fake_init(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(observability.sentry_sdk, "init", fake_init)
    monkeypatch.setattr(
        settings, "sentry_dsn", "https://examplePublicKey@o0.ingest.sentry.io/0"
    )
    monkeypatch.setattr(settings, "environment", "test")
    monkeypatch.setattr(settings, "sentry_traces_sample_rate", 0.0)
    monkeypatch.setattr(observability, "_initialized", False)

    assert observability.init_sentry() is True
    assert captured["dsn"].startswith("https://")
    assert captured["environment"] == "test"
    assert captured["send_default_pii"] is False
