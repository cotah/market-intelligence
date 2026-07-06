"""Integracao com Hacker News (API oficial do Firebase).

API publica e gratuita, sem chave — por isso nao existe modo mock aqui.
Graceful degradation: se a API estiver fora do ar, retorna lista vazia e
loga aviso (o trend_hunter ja lida com fonte vazia). Se um item individual
falhar, a story e pulada e as outras sao mantidas.

Docs: https://github.com/HackerNews/API
"""

import asyncio

import httpx

from core.logging_config import get_logger

log = get_logger("integrations.hackernews")

_BASE_URL = "https://hacker-news.firebaseio.com/v0"
_TIMEOUT = 15.0


async def _fetch_item(client: httpx.AsyncClient, story_id: int) -> dict | None:
    """Busca uma story individual. Retorna None se falhar (o chamador pula)."""
    try:
        response = await client.get(f"{_BASE_URL}/item/{story_id}.json")
        response.raise_for_status()
        item = response.json()
    except Exception as e:  # noqa: BLE001 - item que falha e pulado
        log.warning("hackernews.item_failed", story_id=story_id, error=str(e))
        return None

    if not isinstance(item, dict) or not item.get("title"):
        return None

    return {
        "title": item["title"],
        "score": item.get("score", 0),
        # Ask HN / Show HN sem link externo -> link do proprio item no HN.
        "url": item.get("url") or f"https://news.ycombinator.com/item?id={story_id}",
        "num_comments": item.get("descendants", 0),
        "is_mock": False,
    }


async def get_top_stories(limit: int = 10) -> list[dict]:
    """Retorna as top stories do Hacker News.

    Estrutura: [{"title", "score", "url", "num_comments", "is_mock"}].
    API fora do ar -> lista vazia (nunca lanca excecao).
    """
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        try:
            response = await client.get(f"{_BASE_URL}/topstories.json")
            response.raise_for_status()
            story_ids = response.json()[:limit]
        except Exception as e:  # noqa: BLE001 - API fora -> fonte vazia
            log.warning("hackernews.api_down", error=str(e))
            return []

        items = await asyncio.gather(
            *(_fetch_item(client, story_id) for story_id in story_ids)
        )

    stories = [item for item in items if item is not None]
    log.info("hackernews.completed", results_count=len(stories))
    return stories
