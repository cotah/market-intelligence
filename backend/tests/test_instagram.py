"""Testes da integracao Instagram via Apify (instagram-hashtag-posts-scraper).

Mesmo padrao do reddit.py: dado real quando APIFY_API_TOKEN esta
configurado, mock realista quando o token falta ou a chamada falha
(graceful degradation, com is_mock rastreavel).

Cobre:
- sem token do Apify -> mock
- com token + Apify respondendo -> dados reais (is_mock=False)
- com token mas a chamada ao Apify falha -> cai pro mock
"""

import httpx
import pytest

from core.config import settings
from integrations import instagram


@pytest.fixture(autouse=True)
def _reset_apify_token(monkeypatch):
    monkeypatch.setattr(settings, "apify_api_token", "")


async def test_search_hashtag_uses_mock_without_apify_token():
    results = await instagram.search_hashtag("aireceptionist")

    assert len(results) > 0
    assert all(r["is_mock"] is True for r in results)
    assert all(r["hashtag"] == "aireceptionist" for r in results)


async def test_search_hashtag_uses_real_data_when_apify_token_present(monkeypatch, httpx_mock):
    monkeypatch.setattr(settings, "apify_api_token", "fake_token")

    httpx_mock.add_response(
        url=(
            "https://api.apify.com/v2/acts/breathtaking_anthem~instagram-hashtag-posts-scraper"
            "/run-sync-get-dataset-items?token=fake_token"
        ),
        method="POST",
        json=[
            {
                "caption": "Our AI receptionist answered 200 calls this week #aireceptionist",
                "likesCount": 1543,
            }
        ],
    )

    results = await instagram.search_hashtag("aireceptionist")

    assert len(results) == 1
    assert results[0]["is_mock"] is False
    assert "AI receptionist" in results[0]["caption"]
    assert results[0]["likes"] == 1543
    assert results[0]["hashtag"] == "aireceptionist"


async def test_search_hashtag_falls_back_to_mock_when_apify_fails(monkeypatch, httpx_mock):
    monkeypatch.setattr(settings, "apify_api_token", "fake_token")

    httpx_mock.add_exception(httpx.ConnectTimeout("timed out"), method="POST")

    results = await instagram.search_hashtag("aireceptionist")

    assert len(results) > 0
    assert all(r["is_mock"] is True for r in results)
