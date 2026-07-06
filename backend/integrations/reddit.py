"""Integracao com Reddit via Apify.

A API oficial do Reddit fechou o cadastro self-service em 2026 (Responsible
Builder Policy) — criar credencial nova hoje exige aprovacao manual da
equipe deles, sem prazo garantido. Por isso, a busca real usa um Actor
pronto do Apify (fatihtahta/reddit-scraper-search-fast) em vez de OAuth
direto com o Reddit.

Modo mock: sem APIFY_API_TOKEN, OU se a chamada real falhar por qualquer
motivo — cai num conjunto de posts simulados realistas (graceful
degradation, no mesmo espirito das outras integracoes).

IMPORTANTE no modo mock: tudo e SIMULADO, nao sao posts reais. Cada
resultado tem "is_mock" para deixar isso rastreavel no dado que chega no LLM.
"""

import httpx

from core.config import settings
from core.logging_config import get_logger

log = get_logger("integrations.reddit")

_ACTOR = "fatihtahta~reddit-scraper-search-fast"
_RUN_URL = f"https://api.apify.com/v2/acts/{_ACTOR}/run-sync-get-dataset-items"
_TIMEOUT = 45.0

# Frases de dor genericas e realistas, usadas para montar o mock.
_PAIN_TEMPLATES: list[dict] = [
    {
        "title": "I wish there was a better tool for {topic}",
        "body": "I've tried everything and nothing really solves {topic} for small businesses. Spending hours every week on this manually.",
        "upvotes": 342,
    },
    {
        "title": "Why doesn't anyone fix {topic}?",
        "body": "Seriously, the existing options for {topic} are expensive and clunky. There should be something simpler.",
        "upvotes": 187,
    },
    {
        "title": "I hate how complicated {topic} is",
        "body": "Every solution for {topic} assumes you have a big team. As a solo founder this is impossible to manage.",
        "upvotes": 256,
    },
    {
        "title": "Looking for recommendations on {topic}",
        "body": "Current tools for {topic} keep failing me. Anyone found something that actually works and is affordable?",
        "upvotes": 98,
    },
]


async def _search_real(subreddit: str, query: str) -> list[dict] | None:
    """Busca posts reais via Apify. Retorna None se a chamada falhar
    (o chamador cai no mock nesse caso)."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                _RUN_URL,
                params={"token": settings.apify_api_token},
                json={
                    "subredditName": subreddit,
                    "queries": [query],
                    "maxPosts": 10,
                    "scrapeComments": False,
                },
            )
            response.raise_for_status()
            items = response.json()
    except Exception as e:  # noqa: BLE001 - qualquer falha aqui vira fallback
        log.warning("reddit.apify_failed", error=str(e))
        return None

    return [
        {
            "title": item.get("title", ""),
            "body": (item.get("body") or "")[:1000],
            "upvotes": item.get("score", 0),
            "subreddit": item.get("subreddit", subreddit),
            "is_mock": False,
        }
        for item in items
        if isinstance(item, dict)
    ]


def _mock_results(subreddit: str, query: str) -> list[dict]:
    topic = query.strip() or "this problem"
    results = [
        {
            "title": tpl["title"].format(topic=topic),
            "body": tpl["body"].format(topic=topic),
            "upvotes": tpl["upvotes"],
            "subreddit": subreddit,
            "is_mock": True,
        }
        for tpl in _PAIN_TEMPLATES
    ]
    log.info("reddit.completed", subreddit=subreddit, results_count=len(results), mock=True)
    return results


async def search_reddit(subreddit: str, query: str) -> list[dict]:
    """Retorna discussoes relacionadas a `query` em `subreddit`.

    Usa o Apify (dado real) quando APIFY_API_TOKEN esta configurado. Cai no
    modo simulado se o token faltar, ou se a chamada real falhar por
    qualquer motivo (graceful degradation).

    Estrutura: [{"title", "body", "upvotes", "subreddit", "is_mock"}].
    """
    if settings.apify_api_token:
        real_results = await _search_real(subreddit, query)
        if real_results is not None:
            log.info(
                "reddit.completed",
                subreddit=subreddit,
                results_count=len(real_results),
                mock=False,
            )
            return real_results
        log.warning("reddit.apify_failed_falling_back_to_mock", subreddit=subreddit)

    return _mock_results(subreddit, query)
