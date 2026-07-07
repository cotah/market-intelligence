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
    # Mock tambem carrega post_url (fake) pra pipeline sem token exercitar
    # o fluxo de comentarios (Etapa 2) em modo mock.
    assert all(r["post_url"].startswith("https://www.instagram.com/") for r in results)


async def test_search_hashtag_uses_real_data_when_apify_token_present(monkeypatch, httpx_mock):
    monkeypatch.setattr(settings, "apify_api_token", "fake_token")

    httpx_mock.add_response(
        url=(
            "https://api.apify.com/v2/acts/breathtaking_anthem~instagram-hashtag-posts-scraper"
            "/run-sync-get-dataset-items?token=fake_token"
        ),
        method="POST",
        # O ator exige max_items >= 24 — a Apify rejeita com 400 abaixo disso.
        match_json={"hashtag": "aireceptionist", "scrape_type": "recent", "max_items": 24},
        json=[
            {
                "caption": "Our AI receptionist answered 200 calls this week #aireceptionist",
                "like_count": 1543,
                "url": "https://www.instagram.com/p/ABC123/",
            }
        ],
    )

    results = await instagram.search_hashtag("aireceptionist")

    assert len(results) == 1
    assert results[0]["is_mock"] is False
    assert "AI receptionist" in results[0]["caption"]
    assert results[0]["likes"] == 1543
    assert results[0]["hashtag"] == "aireceptionist"
    assert results[0]["post_url"] == "https://www.instagram.com/p/ABC123/"


async def test_search_hashtag_filters_error_placeholder_items(monkeypatch, httpx_mock):
    """Guard defensivo (simetria com o TikTok): se o ator devolver um
    item-placeholder de erro ({error, errorCode}), ele nao pode virar
    "post real" na pipeline."""
    monkeypatch.setattr(settings, "apify_api_token", "fake_token")

    httpx_mock.add_response(
        url=(
            "https://api.apify.com/v2/acts/breathtaking_anthem~instagram-hashtag-posts-scraper"
            "/run-sync-get-dataset-items?token=fake_token"
        ),
        method="POST",
        json=[
            {
                "error": "This hashtag does not exist.",
                "errorCode": "NOT_FOUND",
                "url": "https://www.instagram.com/explore/tags/aiagentorchestration/",
            }
        ],
    )

    results = await instagram.search_hashtag("aiagentorchestration")

    # Sem posts de verdade -> lista vazia honesta (nao placeholder, nao mock).
    assert results == []


async def test_search_hashtag_falls_back_to_mock_when_apify_fails(monkeypatch, httpx_mock):
    monkeypatch.setattr(settings, "apify_api_token", "fake_token")

    httpx_mock.add_exception(httpx.ConnectTimeout("timed out"), method="POST")

    results = await instagram.search_hashtag("aireceptionist")

    assert len(results) > 0
    assert all(r["is_mock"] is True for r in results)


# --- get_comments (Etapa 2: comentarios de um post especifico) ---

_POST_URL = "https://www.instagram.com/p/ABC123/"


async def test_get_comments_uses_mock_without_apify_token():
    results = await instagram.get_comments(_POST_URL)

    assert len(results) > 0
    assert all(r["is_mock"] is True for r in results)
    assert all(r["post_url"] == _POST_URL for r in results)


async def test_get_comments_uses_real_data_when_apify_token_present(monkeypatch, httpx_mock):
    monkeypatch.setattr(settings, "apify_api_token", "fake_token")

    httpx_mock.add_response(
        url=(
            "https://api.apify.com/v2/acts/apidojo~instagram-comments-scraper-api"
            "/run-sync-get-dataset-items?token=fake_token"
        ),
        method="POST",
        # Fixa o payload: e isso que o ator espera (licao do bug do max_items).
        match_json={"startUrls": [_POST_URL], "maxItems": 20},
        json=[
            {
                "text": "omg this happens to me every single day, I lose so many clients",
                "likeCount": 42,
            }
        ],
    )

    results = await instagram.get_comments(_POST_URL)

    assert len(results) == 1
    assert results[0]["is_mock"] is False
    assert "lose so many clients" in results[0]["text"]
    assert results[0]["likes"] == 42
    assert results[0]["post_url"] == _POST_URL


async def test_get_comments_falls_back_to_mock_when_apify_fails(monkeypatch, httpx_mock):
    monkeypatch.setattr(settings, "apify_api_token", "fake_token")

    httpx_mock.add_exception(httpx.ConnectTimeout("timed out"), method="POST")

    results = await instagram.get_comments(_POST_URL)

    assert len(results) > 0
    assert all(r["is_mock"] is True for r in results)


async def test_get_comments_does_not_leak_token_in_logs(monkeypatch, httpx_mock):
    """HTTPStatusError inclui a URL com ?token=... — o log nao pode vazar
    o token (visto nos logs do Railway em 2026-07-06)."""
    import structlog.testing

    monkeypatch.setattr(settings, "apify_api_token", "super_secret_token")

    httpx_mock.add_response(method="POST", status_code=400, text="bad input")

    with structlog.testing.capture_logs() as logs:
        await instagram.get_comments(_POST_URL)

    assert "super_secret_token" not in str(logs)
