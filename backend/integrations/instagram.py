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

_MOCK_TEMPLATES: list[dict] = [
    {
        "caption": "Finally tried a tool for #{hashtag} and honestly it changed how I run my business",
        "likes": 892,
    },
    {
        "caption": "Why is #{hashtag} still so hard in 2026? Spent the whole morning fighting with it",
        "likes": 431,
    },
    {
        "caption": "Small biz owners: what are you using for #{hashtag}? Nothing I tried actually works",
        "likes": 267,
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
                    "max_items": 10,
                },
            )
            response.raise_for_status()
            items = response.json()
    except Exception as e:  # noqa: BLE001 - qualquer falha aqui vira fallback
        log.warning("instagram.apify_failed", error=str(e))
        return None

    return [
        {
            "caption": (item.get("caption") or "")[:1000],
            "likes": item.get("likesCount", 0),
            "hashtag": hashtag,
            "is_mock": False,
        }
        for item in items
        if isinstance(item, dict)
    ]


def _mock_results(hashtag: str) -> list[dict]:
    results = [
        {
            "caption": tpl["caption"].format(hashtag=hashtag),
            "likes": tpl["likes"],
            "hashtag": hashtag,
            "is_mock": True,
        }
        for tpl in _MOCK_TEMPLATES
    ]
    log.info("instagram.completed", hashtag=hashtag, results_count=len(results), mock=True)
    return results


async def search_hashtag(hashtag: str) -> list[dict]:
    """Retorna posts recentes do Instagram com a hashtag dada.

    Usa o Apify (dado real) quando APIFY_API_TOKEN esta configurado. Cai no
    modo simulado se o token faltar, ou se a chamada real falhar por
    qualquer motivo (graceful degradation).

    Estrutura: [{"caption", "likes", "hashtag", "is_mock"}].
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
