"""Testes da integracao TikTok via Apify (clockworks/tiktok-hashtag-scraper).

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
from integrations import tiktok


@pytest.fixture(autouse=True)
def _reset_apify_token(monkeypatch):
    monkeypatch.setattr(settings, "apify_api_token", "")


async def test_search_hashtag_uses_mock_without_apify_token():
    results = await tiktok.search_hashtag("aireceptionist")

    assert len(results) > 0
    assert all(r["is_mock"] is True for r in results)
    assert all(r["hashtag"] == "aireceptionist" for r in results)
    # Mock tambem carrega post_url (fake) pra pipeline sem token exercitar
    # o fluxo de comentarios (Etapa 2) em modo mock.
    assert all(r["post_url"].startswith("https://www.tiktok.com/") for r in results)


async def test_search_hashtag_uses_real_data_when_apify_token_present(monkeypatch, httpx_mock):
    monkeypatch.setattr(settings, "apify_api_token", "fake_token")

    httpx_mock.add_response(
        url=(
            "https://api.apify.com/v2/acts/clockworks~tiktok-hashtag-scraper"
            "/run-sync-get-dataset-items?token=fake_token"
        ),
        method="POST",
        json=[
            {
                "text": "POV: your AI receptionist books clients while you sleep #aireceptionist",
                "diggCount": 25400,
                "url": "https://www.tiktok.com/@user/video/7300000000000000000",
            }
        ],
    )

    results = await tiktok.search_hashtag("aireceptionist")

    assert len(results) == 1
    assert results[0]["is_mock"] is False
    assert "AI receptionist" in results[0]["description"]
    assert results[0]["likes"] == 25400
    assert results[0]["hashtag"] == "aireceptionist"
    assert results[0]["post_url"] == "https://www.tiktok.com/@user/video/7300000000000000000"


async def test_search_hashtag_filters_error_placeholder_items(monkeypatch, httpx_mock):
    """Hashtag inexistente: o ator devolve UM item-placeholder de erro
    ({error, errorCode, url da PAGINA DA TAG}) — visto em producao em
    2026-07-06. Esse item nao pode virar "post real" (post_url de tag
    quebra o ator de comentarios e polui a evidencia do LLM)."""
    monkeypatch.setattr(settings, "apify_api_token", "fake_token")

    httpx_mock.add_response(
        url=(
            "https://api.apify.com/v2/acts/clockworks~tiktok-hashtag-scraper"
            "/run-sync-get-dataset-items?token=fake_token"
        ),
        method="POST",
        json=[
            {
                "error": "This profile/hashtag does not exist.",
                "errorCode": "NOT_FOUND",
                "url": "https://www.tiktok.com/tag/aiagentorchestration",
                "input": "aiagentorchestration",
            }
        ],
    )

    results = await tiktok.search_hashtag("aiagentorchestration")

    # Sem videos de verdade -> lista vazia honesta (nao placeholder, nao mock).
    assert results == []


async def test_search_hashtag_prefers_web_video_url(monkeypatch, httpx_mock):
    """Quando o item traz webVideoUrl (URL canonica do video no dataset do
    clockworks), ela vence o campo generico url."""
    monkeypatch.setattr(settings, "apify_api_token", "fake_token")

    httpx_mock.add_response(
        url=(
            "https://api.apify.com/v2/acts/clockworks~tiktok-hashtag-scraper"
            "/run-sync-get-dataset-items?token=fake_token"
        ),
        method="POST",
        json=[
            {
                "text": "real video",
                "diggCount": 10,
                "webVideoUrl": "https://www.tiktok.com/@user/video/111",
                "url": "https://www.tiktok.com/tag/something",
            }
        ],
    )

    results = await tiktok.search_hashtag("something")

    assert results[0]["post_url"] == "https://www.tiktok.com/@user/video/111"


async def test_search_hashtag_falls_back_to_mock_when_apify_fails(monkeypatch, httpx_mock):
    monkeypatch.setattr(settings, "apify_api_token", "fake_token")

    httpx_mock.add_exception(httpx.ConnectTimeout("timed out"), method="POST")

    results = await tiktok.search_hashtag("aireceptionist")

    assert len(results) > 0
    assert all(r["is_mock"] is True for r in results)


async def test_search_hashtag_does_not_leak_token_in_logs(monkeypatch, httpx_mock):
    """HTTPStatusError inclui a URL com ?token=... — o log nao pode vazar
    o token (visto nos logs do Railway em 2026-07-06)."""
    import structlog.testing

    monkeypatch.setattr(settings, "apify_api_token", "super_secret_token")

    httpx_mock.add_response(method="POST", status_code=400, text="bad input")

    with structlog.testing.capture_logs() as logs:
        await tiktok.search_hashtag("aireceptionist")

    assert "super_secret_token" not in str(logs)


# --- get_comments (Etapa 2: comentarios de um video especifico) ---

_POST_URL = "https://www.tiktok.com/@user/video/7300000000000000000"


async def test_get_comments_uses_mock_without_apify_token():
    results = await tiktok.get_comments(_POST_URL)

    assert len(results) > 0
    assert all(r["is_mock"] is True for r in results)
    assert all(r["post_url"] == _POST_URL for r in results)


async def test_get_comments_uses_real_data_when_apify_token_present(monkeypatch, httpx_mock):
    monkeypatch.setattr(settings, "apify_api_token", "fake_token")

    httpx_mock.add_response(
        url=(
            "https://api.apify.com/v2/acts/apidojo~tiktok-comments-scraper"
            "/run-sync-get-dataset-items?token=fake_token"
        ),
        method="POST",
        # Fixa o payload: o ator espera startUrls (run FAILED em producao
        # 2026-07-07 com "Start URLs must be provided" ao mandar postURLs).
        match_json={"startUrls": [_POST_URL], "includeReplies": False, "maxItems": 20},
        json=[
            {
                # Dataset real do apidojo~tiktok-comments-scraper usa likeCount
                # (nao diggCount) — visto em teste real na Apify em 2026-07-07.
                "text": "bro I deal with this every day at my salon, it drives me crazy",
                "likeCount": 310,
            }
        ],
    )

    results = await tiktok.get_comments(_POST_URL)

    assert len(results) == 1
    assert results[0]["is_mock"] is False
    assert "drives me crazy" in results[0]["text"]
    assert results[0]["likes"] == 310
    assert results[0]["post_url"] == _POST_URL


async def test_get_comments_falls_back_to_mock_when_apify_fails(monkeypatch, httpx_mock):
    monkeypatch.setattr(settings, "apify_api_token", "fake_token")

    httpx_mock.add_exception(httpx.ConnectTimeout("timed out"), method="POST")

    results = await tiktok.get_comments(_POST_URL)

    assert len(results) > 0
    assert all(r["is_mock"] is True for r in results)
