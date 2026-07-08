"""Testes da integracao Hacker News (API oficial do Firebase).

API publica e sem chave — nao ha modo mock. Graceful degradation:
se a API cair, retorna lista vazia e loga aviso (o trend_hunter ja
lida com fonte vazia).

Cobre:
- API respondendo -> lista de stories com title/score/url/num_comments
- story sem "url" (Ask HN) -> cai no link do proprio HN
- item individual falhando -> pula a story, mantem as outras
- API fora do ar -> lista vazia (nao lanca excecao)
"""

import httpx

from integrations import hackernews

_TOP_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"


def _item_url(story_id: int) -> str:
    return f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"


async def test_get_top_stories_returns_story_details(httpx_mock):
    httpx_mock.add_response(url=_TOP_URL, json=[101, 102])
    httpx_mock.add_response(
        url=_item_url(101),
        json={
            "id": 101,
            "title": "Show HN: I built an AI receptionist",
            "score": 512,
            "url": "https://example.com/ai-receptionist",
            "descendants": 231,
            "type": "story",
        },
    )
    httpx_mock.add_response(
        url=_item_url(102),
        json={
            "id": 102,
            "title": "Ask HN: Why is invoicing still so painful?",
            "score": 340,
            "descendants": 187,
            "type": "story",
        },
    )

    stories = await hackernews.get_top_stories(limit=2)

    assert len(stories) == 2
    assert stories[0] == {
        "title": "Show HN: I built an AI receptionist",
        "score": 512,
        "url": "https://example.com/ai-receptionist",
        "num_comments": 231,
        "is_mock": False,
    }
    # Ask HN nao tem "url" -> link do proprio item no HN.
    assert stories[1]["url"] == "https://news.ycombinator.com/item?id=102"
    assert stories[1]["num_comments"] == 187


async def test_get_top_stories_respects_limit(httpx_mock):
    httpx_mock.add_response(url=_TOP_URL, json=[1, 2, 3, 4, 5])
    for story_id in (1, 2, 3):
        httpx_mock.add_response(
            url=_item_url(story_id),
            json={"id": story_id, "title": f"Story {story_id}", "score": 10, "type": "story"},
        )

    stories = await hackernews.get_top_stories(limit=3)

    assert len(stories) == 3


async def test_get_top_stories_skips_failed_items(httpx_mock):
    httpx_mock.add_response(url=_TOP_URL, json=[201, 202])
    httpx_mock.add_exception(httpx.ReadTimeout("timed out"), url=_item_url(201))
    httpx_mock.add_response(
        url=_item_url(202),
        json={"id": 202, "title": "Surviving story", "score": 99, "type": "story"},
    )

    stories = await hackernews.get_top_stories(limit=2)

    assert len(stories) == 1
    assert stories[0]["title"] == "Surviving story"


async def test_get_top_stories_returns_empty_list_when_api_is_down(httpx_mock):
    httpx_mock.add_exception(httpx.ConnectError("connection refused"), url=_TOP_URL)

    stories = await hackernews.get_top_stories()

    assert stories == []
