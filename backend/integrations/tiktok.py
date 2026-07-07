"""Integracao com TikTok via Apify (tiktok-hashtag-scraper).

O TikTok nao tem API publica de busca por hashtag — a Research API
oficial e restrita a instituicoes academicas. Por isso a busca real usa
um Actor pronto do Apify (clockworks/tiktok-hashtag-scraper).

Modo mock: sem APIFY_API_TOKEN, OU se a chamada real falhar por qualquer
motivo — cai num conjunto de videos simulados realistas (graceful
degradation). Cada resultado tem "is_mock" para deixar isso rastreavel.
"""

import httpx

from core.config import settings
from core.logging_config import get_logger
from core.text import redact_token

log = get_logger("integrations.tiktok")

_ACTOR = "clockworks~tiktok-hashtag-scraper"
_RUN_URL = f"https://api.apify.com/v2/acts/{_ACTOR}/run-sync-get-dataset-items"
_TIMEOUT = 60.0

# Etapa 2: comentarios de um video especifico (evidencia de dor espontanea).
_COMMENTS_ACTOR = "apidojo~tiktok-comments-scraper"
_COMMENTS_RUN_URL = f"https://api.apify.com/v2/acts/{_COMMENTS_ACTOR}/run-sync-get-dataset-items"
_MAX_COMMENTS = 20

_MOCK_COMMENT_TEMPLATES: list[dict] = [
    {"text": "this is so real, I lose customers every week because of this", "likes": 480},
    {"text": "why is there still no good solution for this?? someone please build it", "likes": 190},
    {"text": "I gave up and just do it manually now, huge waste of time", "likes": 65},
]

_MOCK_TEMPLATES: list[dict] = [
    {
        "description": "POV: you finally found something that solves #{hashtag} and it feels illegal",
        "likes": 18200,
        "post_url": "https://www.tiktok.com/@mockuser1/video/7300000000000000001",
    },
    {
        "description": "Nobody talks about how painful #{hashtag} is for small business owners",
        "likes": 7400,
        "post_url": "https://www.tiktok.com/@mockuser2/video/7300000000000000002",
    },
    {
        "description": "Rating every tool I tried for #{hashtag} — most of them failed me",
        "likes": 3100,
        "post_url": "https://www.tiktok.com/@mockuser3/video/7300000000000000003",
    },
]


async def _search_real(hashtag: str) -> list[dict] | None:
    """Busca videos reais via Apify. Retorna None se a chamada falhar
    (o chamador cai no mock nesse caso)."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                _RUN_URL,
                params={"token": settings.apify_api_token},
                json={
                    "hashtags": [hashtag],
                    "resultsPerPage": 10,
                },
            )
            response.raise_for_status()
            items = response.json()
    except Exception as e:  # noqa: BLE001 - qualquer falha aqui vira fallback
        log.warning("tiktok.apify_failed", error=redact_token(str(e)))
        return None

    return [
        {
            "description": (item.get("text") or "")[:1000],
            "likes": item.get("diggCount", 0),
            "hashtag": hashtag,
            # webVideoUrl e a URL canonica do video no dataset do clockworks;
            # "url" pode ser so a pagina da tag.
            "post_url": item.get("webVideoUrl") or item.get("url", ""),
            "is_mock": False,
        }
        for item in items
        # Hashtag inexistente: o ator devolve um item-placeholder com
        # {error, errorCode} — nao e um video, entao fica de fora.
        if isinstance(item, dict) and "error" not in item and "errorCode" not in item
    ]


def _mock_results(hashtag: str) -> list[dict]:
    results = [
        {
            "description": tpl["description"].format(hashtag=hashtag),
            "likes": tpl["likes"],
            "hashtag": hashtag,
            "post_url": tpl["post_url"],
            "is_mock": True,
        }
        for tpl in _MOCK_TEMPLATES
    ]
    log.info("tiktok.completed", hashtag=hashtag, results_count=len(results), mock=True)
    return results


async def _get_comments_real(post_url: str) -> list[dict] | None:
    """Busca comentarios reais de um video via Apify. Retorna None se a
    chamada falhar (o chamador cai no mock nesse caso)."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                _COMMENTS_RUN_URL,
                params={"token": settings.apify_api_token},
                json={
                    "postURLs": [post_url],
                    "includeReplies": False,
                    "maxItems": _MAX_COMMENTS,
                },
            )
            response.raise_for_status()
            items = response.json()
    except httpx.HTTPStatusError as e:
        # Corpo da resposta no log: a Apify explica o motivo ali.
        log.warning(
            "tiktok.comments_apify_failed",
            error=redact_token(str(e)),
            response_body=redact_token(e.response.text[:500]),
        )
        return None
    except Exception as e:  # noqa: BLE001 - qualquer falha aqui vira fallback
        log.warning("tiktok.comments_apify_failed", error=redact_token(str(e)))
        return None

    return [
        {
            "text": (item.get("text") or "")[:1000],
            "likes": item.get("diggCount", 0),
            "post_url": post_url,
            "is_mock": False,
        }
        for item in items
        if isinstance(item, dict)
    ]


def _mock_comments(post_url: str) -> list[dict]:
    results = [
        {
            "text": tpl["text"],
            "likes": tpl["likes"],
            "post_url": post_url,
            "is_mock": True,
        }
        for tpl in _MOCK_COMMENT_TEMPLATES
    ]
    log.info("tiktok.comments_completed", post_url=post_url, results_count=len(results), mock=True)
    return results


async def get_comments(post_url: str) -> list[dict]:
    """Retorna comentarios recentes de um video especifico do TikTok.

    Etapa 2 do problem_hunter: comentario e onde a reacao espontanea
    aparece. Mesmo padrao de graceful degradation do search_hashtag:
    sem token, ou falha na chamada real -> mock.

    Estrutura: [{"text", "likes", "post_url", "is_mock"}].
    """
    if settings.apify_api_token:
        real_results = await _get_comments_real(post_url)
        if real_results is not None:
            log.info(
                "tiktok.comments_completed",
                post_url=post_url,
                results_count=len(real_results),
                mock=False,
            )
            return real_results
        log.warning("tiktok.comments_falling_back_to_mock", post_url=post_url)

    return _mock_comments(post_url)


async def search_hashtag(hashtag: str) -> list[dict]:
    """Retorna videos recentes do TikTok com a hashtag dada.

    Usa o Apify (dado real) quando APIFY_API_TOKEN esta configurado. Cai no
    modo simulado se o token faltar, ou se a chamada real falhar por
    qualquer motivo (graceful degradation).

    Estrutura: [{"description", "likes", "hashtag", "post_url", "is_mock"}].
    """
    if settings.apify_api_token:
        real_results = await _search_real(hashtag)
        if real_results is not None:
            log.info(
                "tiktok.completed",
                hashtag=hashtag,
                results_count=len(real_results),
                mock=False,
            )
            return real_results
        log.warning("tiktok.apify_failed_falling_back_to_mock", hashtag=hashtag)

    return _mock_results(hashtag)
