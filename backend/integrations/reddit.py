"""Integracao com Reddit - MODO MOCK.

A Reddit API tem restricoes para uso automatizado, entao por enquanto
retornamos dados simulados realistas. Quando houver REDDIT_CLIENT_ID /
SECRET, a integracao real pode ser plugada aqui (ex: PRAW/asyncpraw).

IMPORTANTE: tudo abaixo e SIMULADO. Nao sao posts reais.
"""

from core.config import settings
from core.logging_config import get_logger

log = get_logger("integrations.reddit")


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


async def search_reddit(subreddit: str, query: str) -> list[dict]:
    """Retorna discussoes (MOCK) relacionadas a `query` em `subreddit`.

    Estrutura: [{"title", "body", "upvotes", "subreddit", "is_mock"}].
    """
    if settings.reddit_client_id and settings.reddit_client_secret:
        # Ponto de extensao: integracao real (asyncpraw) entraria aqui.
        log.info("reddit.real_api_not_implemented", note="usando mock mesmo com credenciais")

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
