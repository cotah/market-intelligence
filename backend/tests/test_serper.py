"""Testes da integracao Serper (Google Search API).

Foco: o log de falha precisa incluir o corpo da resposta — "400 Bad
Request" sozinho esconde o motivo real (ex.: "Not enough credits",
visto em producao 2026-07-07).
"""

import pytest

from core.config import settings
from integrations import serper


@pytest.fixture(autouse=True)
def _fake_serper_key(monkeypatch):
    monkeypatch.setattr(settings, "serper_api_key", "fake_key")


async def test_google_search_logs_response_body_on_http_error(httpx_mock):
    import structlog.testing

    httpx_mock.add_response(
        method="POST",
        status_code=400,
        json={"message": "Not enough credits", "statusCode": 400},
    )

    with structlog.testing.capture_logs() as logs:
        results = await serper.google_search("trending topics")

    assert results == []
    failures = [entry for entry in logs if entry["event"] == "serper.failed"]
    assert failures
    assert "Not enough credits" in failures[0]["response_body"]
