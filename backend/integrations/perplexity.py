"""Integracao com Perplexity (pesquisa de mercado profunda, online).

Graceful degradation: se a chave faltar ou a API falhar, retorna string
vazia e loga o motivo, em vez de quebrar o agente.
"""

import httpx

from core.config import settings
from core.logging_config import get_logger

log = get_logger("integrations.perplexity")

_API_URL = "https://api.perplexity.ai/chat/completions"
_TIMEOUT = 60.0


async def search(query: str, focus: str = "internet") -> str:
    """Pesquisa no Perplexity e retorna o conteudo da resposta como string."""
    if not settings.perplexity_api_key:
        log.warning("perplexity.skipped", reason="no_api_key")
        return ""

    headers = {
        "Authorization": f"Bearer {settings.perplexity_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.perplexity_model,
        "messages": [
            {
                "role": "system",
                "content": f"You are a market research assistant. Focus on {focus}. Be concise and cite sources.",
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
            # Limita o retorno: respostas muito longas estouravam o prompt do
            # Claude (400). 3000 chars sao suficientes para os agentes.
            content = content[:3000]
            log.info("perplexity.completed", chars=len(content))
            return content
    except Exception as e:  # noqa: BLE001 - degradacao graciosa
        log.error("perplexity.failed", error=str(e))
        return ""
