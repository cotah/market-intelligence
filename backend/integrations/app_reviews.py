"""Integracao com reviews da App Store (Apify + iTunes Search API).

Duas pecas:
- find_app(topic): iTunes Search API oficial (gratis, sem chave) para
  mapear um topico de negocio -> app mais relevante da App Store. Sem
  app encontrado ou API fora -> None (o problem_hunter pula a fonte).
- get_reviews(app_id): reviews reais via Actor do Apify
  (thewolves/appstore-reviews-scraper). Mesmo padrao do reddit.py:
  sem APIFY_API_TOKEN ou chamada falhando -> mock realista com
  is_mock rastreavel (graceful degradation).

Reviews de app sao otima fonte de dor: usuarios reclamam do que falta
nos concorrentes existentes.
"""

import httpx

from core.config import settings
from core.logging_config import get_logger

log = get_logger("integrations.app_reviews")

_ITUNES_SEARCH_URL = "https://itunes.apple.com/search"
_ACTOR = "thewolves~appstore-reviews-scraper"
_RUN_URL = f"https://api.apify.com/v2/acts/{_ACTOR}/run-sync-get-dataset-items"
_TIMEOUT = 60.0

_MOCK_TEMPLATES: list[dict] = [
    {
        "title": "Great idea, frustrating execution",
        "body": "The concept is exactly what I needed but it keeps losing my data and support never answers.",
        "rating": 2,
    },
    {
        "title": "Too expensive for what it does",
        "body": "The free tier is useless and the paid plan costs more than tools that do twice as much.",
        "rating": 3,
    },
    {
        "title": "Almost perfect",
        "body": "Works well overall, but I wish it integrated with the other tools I already use daily.",
        "rating": 4,
    },
]


async def find_app(topic: str) -> dict | None:
    """Mapeia um topico -> app mais relevante da App Store (iTunes Search).

    Retorna {"app_id": str, "name": str} ou None se nao achar app /
    API estiver fora (o chamador pula essa fonte nesse caso).
    """
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.get(
                _ITUNES_SEARCH_URL,
                params={"term": topic, "entity": "software", "limit": 3},
            )
            response.raise_for_status()
            results = response.json().get("results", [])
    except Exception as e:  # noqa: BLE001 - API fora -> fonte pulada
        log.warning("app_reviews.itunes_search_failed", topic=topic, error=str(e))
        return None

    if not results or not results[0].get("trackId"):
        log.info("app_reviews.no_app_found", topic=topic)
        return None

    app = {"app_id": str(results[0]["trackId"]), "name": results[0].get("trackName", "")}
    log.info("app_reviews.app_found", topic=topic, app_id=app["app_id"], name=app["name"])
    return app


async def _get_reviews_real(app_id: str) -> list[dict] | None:
    """Busca reviews reais via Apify. Retorna None se a chamada falhar
    (o chamador cai no mock nesse caso)."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                _RUN_URL,
                params={"token": settings.apify_api_token},
                json={
                    "appIds": [app_id],
                    "country": "us",
                    "maxItems": 20,
                },
            )
            response.raise_for_status()
            items = response.json()
    except Exception as e:  # noqa: BLE001 - qualquer falha aqui vira fallback
        log.warning("app_reviews.apify_failed", error=str(e))
        return None

    return [
        {
            "title": item.get("title", ""),
            "body": (item.get("review") or "")[:1000],
            "rating": item.get("rating", 0),
            "is_mock": False,
        }
        for item in items
        if isinstance(item, dict)
    ]


def _mock_results(app_id: str) -> list[dict]:
    results = [{**tpl, "is_mock": True} for tpl in _MOCK_TEMPLATES]
    log.info("app_reviews.completed", app_id=app_id, results_count=len(results), mock=True)
    return results


async def get_reviews(app_id: str) -> list[dict]:
    """Retorna reviews da App Store para o app dado.

    Usa o Apify (dado real) quando APIFY_API_TOKEN esta configurado. Cai no
    modo simulado se o token faltar, ou se a chamada real falhar por
    qualquer motivo (graceful degradation).

    Estrutura: [{"title", "body", "rating", "is_mock"}].
    """
    if settings.apify_api_token:
        real_results = await _get_reviews_real(app_id)
        if real_results is not None:
            log.info(
                "app_reviews.completed",
                app_id=app_id,
                results_count=len(real_results),
                mock=False,
            )
            return real_results
        log.warning("app_reviews.apify_failed_falling_back_to_mock", app_id=app_id)

    return _mock_results(app_id)
