"""Cache Redis para chamadas de APIs pagas (Serper, Apify).

A mesma query repetida dentro do TTL (24h por padrao) nao paga credito
duas vezes. Tudo degrada graciosamente: Redis fora -> chama a API
normalmente, como se o cache nao existisse (mesmo espirito do
pipeline_control.py).

Regras:
- So cacheia resultado real e NAO-vazio. Falha (None) ou lista vazia
  nao entra no cache — senao um erro temporario "esconderia" a
  recuperacao da API ate o TTL expirar.
- Chave: apicache:{fonte}:{hash dos argumentos} (JSON ordenado, entao
  a mesma query gera sempre a mesma chave).
"""

import hashlib
import json
from collections.abc import Awaitable, Callable
from typing import TypeVar

import redis.asyncio as aioredis

from core.config import settings
from core.logging_config import get_logger

log = get_logger("api_cache")

_KEY_PREFIX = "apicache"


def _make_key(source: str, key_parts: dict) -> str:
    digest = hashlib.sha256(
        json.dumps(key_parts, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:16]
    return f"{_KEY_PREFIX}:{source}:{digest}"


# Tipo do dado cacheado: o retorno de cached() e exatamente o tipo do fetch
# (list[dict], dict, etc.) — cache nao muda a forma do dado.
T = TypeVar("T")


def _client() -> aioredis.Redis:
    return aioredis.Redis.from_url(settings.redis_url, decode_responses=True)


async def cached(
    source: str,
    key_parts: dict,
    fetch: Callable[[], Awaitable[T]],
) -> T:
    """Retorna o valor em cache para (source, key_parts) ou chama fetch().

    Resultado nao-vazio de fetch() e gravado com TTL de
    settings.api_cache_ttl_seconds. Redis indisponivel nunca quebra a
    chamada: o fetch acontece normalmente, so sem economia.
    """
    key = _make_key(source, key_parts)
    client = _client()
    try:
        try:
            raw = await client.get(key)
            if raw is not None:
                log.info("api_cache.hit", source=source, key=key)
                return json.loads(raw)
        except Exception as e:  # noqa: BLE001 - cache nunca derruba a chamada
            log.warning("api_cache.get_failed", source=source, error=str(e))

        log.info("api_cache.miss", source=source, key=key)
        result = await fetch()

        # None (falha) e vazio (sem resultados) ficam de fora do cache.
        if result:
            try:
                await client.set(
                    key,
                    json.dumps(result, ensure_ascii=False),
                    ex=settings.api_cache_ttl_seconds,
                )
                log.info("api_cache.stored", source=source, key=key)
            except Exception as e:  # noqa: BLE001 - cache nunca derruba a chamada
                log.warning("api_cache.set_failed", source=source, error=str(e))

        return result
    finally:
        try:
            await client.aclose()
        except Exception:  # noqa: BLE001 - fechar conexao nunca derruba nada
            pass
