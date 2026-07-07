"""Testes do cache Redis de APIs pagas (core/api_cache.py).

Regras cobertas:
- miss -> chama fetch e grava o resultado com TTL
- hit -> devolve do cache SEM chamar fetch (a economia de credito)
- resultado vazio ou None NUNCA entra no cache
- Redis fora -> fetch acontece normalmente (graceful degradation)
"""

import json

import pytest

from core import api_cache
from core.config import settings


class _FakeRedis:
    """Redis assincrono em memoria, so com o que o api_cache usa."""

    def __init__(self):
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex=None):
        self.store[key] = value
        if ex is not None:
            self.ttls[key] = ex

    async def aclose(self):
        pass


@pytest.fixture
def fake_redis(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(api_cache, "_client", lambda: fake)
    return fake


async def test_miss_chama_fetch_e_grava_com_ttl(fake_redis):
    async def fetch():
        return [{"title": "resultado real"}]

    result = await api_cache.cached("serper", {"query": "ai tools"}, fetch)

    assert result == [{"title": "resultado real"}]
    assert len(fake_redis.store) == 1
    stored = json.loads(next(iter(fake_redis.store.values())))
    assert stored == [{"title": "resultado real"}]
    assert next(iter(fake_redis.ttls.values())) == settings.api_cache_ttl_seconds


async def test_hit_devolve_do_cache_sem_chamar_fetch(fake_redis):
    key = api_cache._make_key("serper", {"query": "ai tools"})
    fake_redis.store[key] = json.dumps([{"title": "do cache"}])

    async def fetch():
        raise AssertionError("fetch nao deveria ser chamado num hit")

    result = await api_cache.cached("serper", {"query": "ai tools"}, fetch)

    assert result == [{"title": "do cache"}]


async def test_mesma_query_gera_mesma_chave_e_ordem_nao_importa():
    key_a = api_cache._make_key("reddit", {"subreddit": "saas", "query": "crm"})
    key_b = api_cache._make_key("reddit", {"query": "crm", "subreddit": "saas"})
    key_c = api_cache._make_key("reddit", {"subreddit": "saas", "query": "outra"})

    assert key_a == key_b
    assert key_a != key_c


async def test_resultado_vazio_nao_entra_no_cache(fake_redis):
    async def fetch_vazio():
        return []

    result = await api_cache.cached("serper", {"query": "sem resultados"}, fetch_vazio)

    assert result == []
    assert fake_redis.store == {}


async def test_resultado_none_nao_entra_no_cache(fake_redis):
    async def fetch_falha():
        return None

    result = await api_cache.cached("instagram.hashtag", {"hashtag": "x"}, fetch_falha)

    assert result is None
    assert fake_redis.store == {}


async def test_redis_fora_nao_quebra_a_chamada():
    # Sem fixture fake_redis: vale a autouse do conftest (_RedisDown).
    async def fetch():
        return [{"title": "veio da API mesmo sem cache"}]

    result = await api_cache.cached("serper", {"query": "qualquer"}, fetch)

    assert result == [{"title": "veio da API mesmo sem cache"}]
