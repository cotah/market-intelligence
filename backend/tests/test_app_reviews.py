"""Testes da integracao App Store Reviews (Apify + iTunes Search API).

Duas pecas:
- find_app(topic): iTunes Search API (gratis, sem chave) para mapear
  topico -> app mais relevante. Sem app ou API fora -> None (o
  problem_hunter pula a fonte nesse caso).
- get_reviews(app_id): actor do Apify (thewolves/appstore-reviews-scraper),
  mesmo padrao do reddit.py (mock sem token ou em falha, is_mock rastreavel).

Cobre:
- find_app com resultado -> app_id + name do mais relevante
- find_app sem resultado -> None
- find_app com API fora -> None
- get_reviews sem token -> mock
- get_reviews com token + Apify respondendo -> dados reais
- get_reviews com token mas Apify falhando -> mock
"""

import httpx
import pytest

from core.config import settings
from integrations import app_reviews


@pytest.fixture(autouse=True)
def _reset_apify_token(monkeypatch):
    monkeypatch.setattr(settings, "apify_api_token", "")


# --- find_app (iTunes Search API) ---


async def test_find_app_returns_most_relevant_app(httpx_mock):
    httpx_mock.add_response(
        url="https://itunes.apple.com/search?term=invoicing&entity=software&limit=3",
        json={
            "resultCount": 2,
            "results": [
                {"trackId": 123456, "trackName": "Invoice Maker Pro"},
                {"trackId": 789012, "trackName": "Billing Buddy"},
            ],
        },
    )

    app = await app_reviews.find_app("invoicing")

    assert app == {"app_id": "123456", "name": "Invoice Maker Pro"}


async def test_find_app_returns_none_when_no_results(httpx_mock):
    httpx_mock.add_response(
        url="https://itunes.apple.com/search?term=xyzzy&entity=software&limit=3",
        json={"resultCount": 0, "results": []},
    )

    assert await app_reviews.find_app("xyzzy") is None


async def test_find_app_returns_none_when_itunes_is_down(httpx_mock):
    httpx_mock.add_exception(httpx.ConnectError("connection refused"))

    assert await app_reviews.find_app("invoicing") is None


# --- get_reviews (Apify) ---


async def test_get_reviews_uses_mock_without_apify_token():
    results = await app_reviews.get_reviews("123456")

    assert len(results) > 0
    assert all(r["is_mock"] is True for r in results)
    assert all(1 <= r["rating"] <= 5 for r in results)


async def test_get_reviews_uses_real_data_when_apify_token_present(monkeypatch, httpx_mock):
    monkeypatch.setattr(settings, "apify_api_token", "fake_token")

    httpx_mock.add_response(
        url=(
            "https://api.apify.com/v2/acts/thewolves~appstore-reviews-scraper"
            "/run-sync-get-dataset-items?token=fake_token"
        ),
        method="POST",
        json=[
            {
                "title": "Crashes every time I export",
                "review": "I love the app but it crashes whenever I try to export a PDF invoice.",
                "rating": 2,
            }
        ],
    )

    results = await app_reviews.get_reviews("123456")

    assert len(results) == 1
    assert results[0] == {
        "title": "Crashes every time I export",
        "body": "I love the app but it crashes whenever I try to export a PDF invoice.",
        "rating": 2,
        "is_mock": False,
    }


async def test_get_reviews_falls_back_to_mock_when_apify_fails(monkeypatch, httpx_mock):
    monkeypatch.setattr(settings, "apify_api_token", "fake_token")

    httpx_mock.add_exception(httpx.ConnectTimeout("timed out"), method="POST")

    results = await app_reviews.get_reviews("123456")

    assert len(results) > 0
    assert all(r["is_mock"] is True for r in results)
