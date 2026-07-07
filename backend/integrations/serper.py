"""Integracao com Serper (Google Search API).

Graceful degradation: sem chave ou em caso de erro, retorna lista vazia.
"""

import httpx

from core import summarize
from core.config import settings
from core.logging_config import get_logger

log = get_logger("integrations.serper")

# Acima disso, o conteudo dos snippets somados e resumido antes de seguir.
_CONDENSE_THRESHOLD = 2000

_API_URL = "https://google.serper.dev/search"
_TIMEOUT = 30.0


async def google_search(query: str, num_results: int = 10) -> list[dict]:
    """Busca no Google via Serper. Retorna [{title, link, snippet}, ...]."""
    if not settings.serper_api_key:
        log.warning("serper.skipped", reason="no_api_key")
        return []

    headers = {
        "X-API-KEY": settings.serper_api_key,
        "Content-Type": "application/json",
    }
    payload = {"q": query, "num": num_results}

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(_API_URL, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            results = [
                {
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                }
                for item in data.get("organic", [])
            ]

            # Se o conteudo somado dos snippets for grande, condensa em uma
            # unica entrada-resumo (mantem o contrato list[dict] dos agentes).
            combined = "\n".join(f"{r['title']}: {r['snippet']}" for r in results)
            if len(combined) > _CONDENSE_THRESHOLD:
                summary = await summarize.condense(combined, source="serper")
                results = [{"title": "Resumo da pesquisa", "link": "", "snippet": summary}]

            log.info("serper.completed", results_count=len(results))
            return results
    except httpx.HTTPStatusError as e:
        # Corpo da resposta no log: "400" sozinho esconde o motivo real
        # (ex.: "Not enough credits", visto em producao 2026-07-07).
        log.error(
            "serper.failed",
            error=str(e),
            response_body=e.response.text[:500],
        )
        return []
    except Exception as e:  # noqa: BLE001 - degradacao graciosa
        log.error("serper.failed", error=str(e), error_type=type(e).__name__)
        return []
