"""Fixtures compartilhadas dos testes.

O cache de APIs (core/api_cache.py) fala com Redis. Nos testes, nenhum
Redis deve ser tocado: um Redis local ligado faria testes gravarem/lerem
cache de verdade (resultados poluidos e flaky). A fixture autouse abaixo
simula "Redis fora" — o caminho de graceful degradation, em que toda
chamada vai direto pro fetch, exatamente o comportamento antigo.

Testes do proprio api_cache substituem o cliente por um fake funcional
(monkeypatch por cima desta fixture).
"""

import pytest

from core import api_cache


class _RedisDown:
    """Cliente Redis que falha em tudo (simula Redis indisponivel)."""

    async def get(self, key):
        raise ConnectionError("redis indisponivel (teste)")

    async def set(self, key, value, ex=None):
        raise ConnectionError("redis indisponivel (teste)")

    async def aclose(self):
        pass


@pytest.fixture(autouse=True)
def _no_real_redis(monkeypatch):
    monkeypatch.setattr(api_cache, "_client", lambda: _RedisDown())
