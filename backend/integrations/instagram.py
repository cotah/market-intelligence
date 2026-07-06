"""Integracao com Instagram via Apify (hashtag posts scraper).

O Instagram nao tem API publica de busca por hashtag — a Graph API oficial
exige app aprovado em business review. Por isso a busca real usa um Actor
pronto do Apify (breathtaking_anthem/instagram-hashtag-posts-scraper).

Modo mock: sem APIFY_API_TOKEN, OU se a chamada real falhar por qualquer
motivo — cai num conjunto de posts simulados realistas (graceful
degradation). Cada resultado tem "is_mock" para deixar isso rastreavel.
"""

import httpx

from core.config import settings
from core.logging_config import get_logger

log = get_logger("integrations.instagram")

_ACTOR = "breathtaking_anthem~instagram-hashtag-posts-scraper"
_RUN_URL = f"https://api.apify.com/v2/acts/{_ACTOR}/run-sync-get-dataset-items"
_TIMEOUT = 60.0
# O ator valida max_items >= 24 (abaixo disso a Apify responde 400 sem criar run).
_APIFY_MIN_ITEMS = 24
# Quantos posts realmente usamos na pipeline (mesmo volume de antes).
_MAX_RESULTS = 10

# Etapa 2: comentarios de um post especifico (evidencia de dor espontanea).
_COMMENTS_ACTOR = "apidojo~instagram-comments-scraper-api"
_COMMENTS_RUN_URL = f"https://api.apify.com/v2/acts/{_COMMENTS_ACTOR}/run-sync-get-dataset-items"
_MAX_COMMENTS = 20

_MOCK_COMMENT_TEMPLATES: list[dict] = [
    {"text": "omg this is literally my biggest struggle, nothing out there works", "likes": 57},
    {"text": "I wish someone would finally fix this, I waste hours every week on it", "likes": 23},
    {"text": "same here!! tried 3 different tools and gave up on all of them", "likes": 11},
]

_MOCK_TEMPLATES: list[dict] = [
    {
        "caption": "Finally tried a tool for #{hashtag} and honestly it changed how I run my business",
        "likes": 892,
        "post_url": "https://www.instagram.com/p/MOCK00001/",
    },
    {
        "caption": "Why is #{hashtag} still so hard in 2026? Spent the whole morning fighting with it",
        "likes": 431,
        "post_url": "https://www.instagram.com/p/MOCK00002/",
    },
    {
        "caption": "Small biz owners: what are you using for #{hashtag}? Nothing I tried actually works",
        "likes": 267,
        "post_url": "https://www.instagram.com/p/MOCK00003/",
    },
]


async def _search_real(hashtag: str) -> list[dict] | None:
    """Busca posts reais via Apify. Retorna None se a chamada falhar
    (o chamador cai no mock nesse caso)."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                _RUN_URL,
                params={"token": settings.apify_api_token},
                json={
                    "hashtag": hashtag,
                    "scrape_type": "recent",
                    "max_items": _APIFY_MIN_ITEMS,
                },
            )
            response.raise_for_status()
            items = response.json()
    except httpx.HTTPStatusError as e:
        # Inclui o corpo da resposta no log — a Apify explica o motivo ali
        # (ex.: invalid-input), e so o status "400" nao diz nada.
        log.warning(
            "instagram.apify_failed",
            error=str(e),
            response_body=e.response.text[:500],
        )
        return None
    except Exception as e:  # noqa: BLE001 - qualquer falha aqui vira fallback
        log.warning("instagram.apify_failed", error=str(e))
        return None

    return [
        {
            "caption": (item.get("caption") or "")[:1000],
            "likes": item.get("like_count", 0),
            "hashtag": hashtag,
            "post_url": item.get("url", ""),
            "is_mock": False,
        }
        for item in items
        if isinstance(item, dict)
    ][:_MAX_RESULTS]


def _mock_results(hashtag: str) -> list[dict]:
    results = [
        {
            "caption": tpl["caption"].format(hashtag=hashtag),
            "likes": tpl["likes"],
            "hashtag": hashtag,
            "post_url": tpl["post_url"],
            "is_mock": True,
        }
        for tpl in _MOCK_TEMPLATES
    ]
    log.info("instagram.completed", hashtag=hashtag, results_count=len(results), mock=True)
    return results


async def _get_comments_real(post_url: str) -> list[dict] | None:
    """Busca comentarios reais de um post via Apify. Retorna None se a
    chamada falhar (o chamador cai no mock nesse caso)."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                _COMMENTS_RUN_URL,
                params={"token": settings.apify_api_token},
                json={
                    "startUrls": [post_url],
                    "maxItems": _MAX_COMMENTS,
                },
            )
            response.raise_for_status()
            items = response.json()
    except httpx.HTTPStatusError as e:
        # Corpo da resposta no log: a Apify explica o motivo ali.
        log.warning(
            "instagram.comments_apify_failed",
            error=str(e),
            response_body=e.response.text[:500],
        )
        return None
    except Exception as e:  # noqa: BLE001 - qualquer falha aqui vira fallback
        log.warning("instagram.comments_apify_failed", error=str(e))
        return None

    return [
        {
            "text": (item.get("text") or "")[:1000],
            "likes": item.get("likeCount", 0),
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
    log.info("instagram.comments_completed", post_url=post_url, results_count=len(results), mock=True)
    return results


async def get_comments(post_url: str) -> list[dict]:
    """Retorna comentarios recentes de um post especifico do Instagram.

    Etapa 2 do problem_hunter: comentario e onde a reacao espontanea
    aparece (mais parecido com evidencia de dor do Reddit do que a
    legenda do post). Mesmo padrao de graceful degradation do
    search_hashtag: sem token, ou falha na chamada real -> mock.

    Estrutura: [{"text", "likes", "post_url", "is_mock"}].
    """
    if settings.apify_api_token:
        real_results = await _get_comments_real(post_url)
        if real_results is not None:
            log.info(
                "instagram.comments_completed",
                post_url=post_url,
                results_count=len(real_results),
                mock=False,
            )
            return real_results
        log.warning("instagram.comments_falling_back_to_mock", post_url=post_url)

    return _mock_comments(post_url)


async def search_hashtag(hashtag: str) -> list[dict]:
    """Retorna posts recentes do Instagram com a hashtag dada.

    Usa o Apify (dado real) quando APIFY_API_TOKEN esta configurado. Cai no
    modo simulado se o token faltar, ou se a chamada real falhar por
    qualquer motivo (graceful degradation).

    Estrutura: [{"caption", "likes", "hashtag", "post_url", "is_mock"}].
    """
    if settings.apify_api_token:
        real_results = await _search_real(hashtag)
        if real_results is not None:
            log.info(
                "instagram.completed",
                hashtag=hashtag,
                results_count=len(real_results),
                mock=False,
            )
            return real_results
        log.warning("instagram.apify_failed_falling_back_to_mock", hashtag=hashtag)

    return _mock_results(hashtag)
