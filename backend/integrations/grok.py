"""Integracao com Grok (xAI) para pesquisar discussoes no X/Twitter.

Graceful degradation: sem chave ou em caso de erro, retorna string vazia.
"""

import httpx

from core.config import settings
from core.logging_config import get_logger

log = get_logger("integrations.grok")

_API_URL = "https://api.x.ai/v1/chat/completions"
_TIMEOUT = 60.0


async def search_x(query: str) -> str:
    """Pesquisa o que esta sendo discutido no X e retorna texto."""
    if not settings.grok_api_key:
        log.warning("grok.skipped", reason="no_api_key")
        return ""

    headers = {
        "Authorization": f"Bearer {settings.grok_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.grok_model,
        "messages": [
            {
                "role": "system",
                "content": "You research current discussions and trends on X/Twitter. Summarize what people are actively talking about, with concrete examples.",
            },
            {"role": "user", "content": query},
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(_API_URL, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            log.info("grok.completed", chars=len(content))
            return content
    except Exception as e:  # noqa: BLE001 - degradacao graciosa
        log.error("grok.failed", error=str(e))
        return ""
