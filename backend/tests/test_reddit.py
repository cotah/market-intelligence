"""Testes da integracao Reddit via Apify (fatihtahta/reddit-scraper-search-fast).

A API oficial do Reddit fechou o cadastro self-service em 2026 (Responsible
Builder Policy), entao a busca real de posts passou a usar um Actor pronto
do Apify em vez de OAuth direto com o Reddit.

Cobre:
- sem token do Apify -> mock (comportamento ja existente, nao pode regredir)
- com token + Apify respondendo -> dados reais (is_mock=False)
- com token mas a chamada ao Apify falha -> cai pro mock (graceful degradation)
"""

import httpx
import pytest

from core.config import settings
from integrations import reddit


@pytest.fixture(autouse=True)
def _reset_apify_token(monkeypatch):
    monkeypatch.setattr(settings, "apify_api_token", "")


async def test_search_reddit_uses_mock_without_apify_token():
    results = await reddit.search_reddit("startups", "invoicing")

    assert len(results) > 0
    assert all(r["is_mock"] is True for r in results)
    assert all("invoicing" in r["title"] or "invoicing" in r["body"] for r in results)


async def test_search_reddit_uses_real_data_when_apify_token_present(monkeypatch, httpx_mock):
    monkeypatch.setattr(settings, "apify_api_token", "fake_token")

    httpx_mock.add_response(
        url=(
            "https://api.apify.com/v2/acts/fatihtahta~reddit-scraper-search-fast"
            "/run-sync-get-dataset-items?token=fake_token"
        ),
        method="POST",
        json=[
            {
                "title": "How do you all handle invoicing? I'm embarrassed by my process",
                "body": "I copy an old Word doc, change the client name, chase payments manually...",
                "score": 421,
                "subreddit": "smallbusiness",
            }
        ],
    )

    results = await reddit.search_reddit("startups", "invoicing")

    assert len(results) == 1
    assert results[0]["is_mock"] is False
    assert "invoicing" in results[0]["title"].lower()
    assert results[0]["upvotes"] == 421
    assert results[0]["subreddit"] == "smallbusiness"


async def test_search_reddit_falls_back_to_mock_when_apify_fails(monkeypatch, httpx_mock):
    monkeypatch.setattr(settings, "apify_api_token", "fake_token")

    httpx_mock.add_exception(httpx.ConnectTimeout("timed out"), method="POST")

    results = await reddit.search_reddit("startups", "invoicing")

    assert len(results) > 0
    assert all(r["is_mock"] is True for r in results)
