"""Testes da integracao Google Trends (pytrends).

A pytrends e sincrona e fala com o Google por scraping — nos testes,
monkeypatchamos `_fetch_sync` (a unica funcao que toca a rede) e testamos
a logica de cima: calculo de trend_direction e graceful degradation.

Cobre:
- serie crescente -> trend_direction "rising"
- serie decrescente -> "falling"
- serie estavel -> "stable"
- _fetch_sync falhando (None ou excecao) -> get_trend_score retorna None
- serie vazia -> None (sem dado nao e dado)
"""


from integrations import google_trends


def _series(values: list[int]) -> list[dict]:
    return [
        {"date": f"2026-{(i % 12) + 1:02d}-01", "value": value}
        for i, value in enumerate(values)
    ]


def _patch_fetch(monkeypatch, result):
    def fake_fetch(keyword: str):
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(google_trends, "_fetch_sync", fake_fetch)


async def test_rising_series_returns_rising_direction(monkeypatch):
    series = _series([10, 12, 15, 20, 35, 48, 60, 75])
    _patch_fetch(monkeypatch, series)

    result = await google_trends.get_trend_score("ai receptionist")

    assert result == {
        "keyword": "ai receptionist",
        "interest_over_time": series,
        "trend_direction": "rising",
        "is_mock": False,
    }


async def test_falling_series_returns_falling_direction(monkeypatch):
    _patch_fetch(monkeypatch, _series([80, 75, 60, 50, 30, 22, 15, 10]))

    result = await google_trends.get_trend_score("nft marketplace")

    assert result is not None
    assert result["trend_direction"] == "falling"


async def test_stable_series_returns_stable_direction(monkeypatch):
    _patch_fetch(monkeypatch, _series([50, 52, 49, 51, 50, 48, 52, 50]))

    result = await google_trends.get_trend_score("crm software")

    assert result is not None
    assert result["trend_direction"] == "stable"


async def test_fetch_returning_none_yields_none(monkeypatch):
    _patch_fetch(monkeypatch, None)

    assert await google_trends.get_trend_score("anything") is None


async def test_fetch_raising_yields_none(monkeypatch):
    _patch_fetch(monkeypatch, RuntimeError("429 rate limited"))

    assert await google_trends.get_trend_score("anything") is None


async def test_empty_series_yields_none(monkeypatch):
    _patch_fetch(monkeypatch, [])

    assert await google_trends.get_trend_score("obscure keyword") is None
