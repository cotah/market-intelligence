"""Integracao com Google Trends via pytrends (nao oficial, gratuita).

Nao existe API oficial do Google Trends — a pytrends raspa o endpoint
interno do Google, entao rate limits (429) sao esperados e frequentes.
Por isso a regra aqui e: QUALQUER falha (rate limit, sem dado, erro de
rede) retorna None e o chamador mantem a estimativa do LLM. Dado real
quando da, achismo quando nao da.

A pytrends e sincrona (requests + pandas) — o trabalho de rede fica
isolado em `_fetch_sync`, rodada num thread via asyncio.to_thread para
nao bloquear o event loop.
"""

import asyncio

from core.logging_config import get_logger

log = get_logger("integrations.google_trends")

_TIMEFRAME = "today 3-m"

# Variacao entre a media da metade recente e da metade antiga da serie
# a partir da qual consideramos a tendencia "rising" ou "falling".
_DIRECTION_THRESHOLD = 0.2


def _fetch_sync(keyword: str) -> list[dict] | None:
    """Busca o interesse ao longo do tempo no Google Trends (bloqueante).

    Retorna [{"date": "2026-06-01", "value": 45}, ...] ou None se nao
    houver dado. Import local: pytrends puxa pandas (~60MB), so paga o
    custo quem realmente chama.
    """
    from pytrends.request import TrendReq

    pytrends = TrendReq(hl="en-US", tz=0)
    pytrends.build_payload([keyword], timeframe=_TIMEFRAME)
    df = pytrends.interest_over_time()
    if df.empty or keyword not in df.columns:
        return None

    return [
        {"date": index.strftime("%Y-%m-%d"), "value": int(value)}
        for index, value in df[keyword].items()
    ]


def _trend_direction(values: list[int]) -> str:
    """Compara a media da metade recente com a da metade antiga."""
    half = len(values) // 2
    old_avg = sum(values[:half]) / max(half, 1)
    recent_avg = sum(values[half:]) / max(len(values) - half, 1)

    if old_avg == 0:
        return "rising" if recent_avg > 0 else "stable"

    change = (recent_avg - old_avg) / old_avg
    if change > _DIRECTION_THRESHOLD:
        return "rising"
    if change < -_DIRECTION_THRESHOLD:
        return "falling"
    return "stable"


async def get_trend_score(keyword: str) -> dict | None:
    """Retorna o interesse real de busca por `keyword` no Google Trends.

    Estrutura: {"keyword", "interest_over_time", "trend_direction", "is_mock"}.
    Qualquer falha (rate limit, sem dado) -> None; o chamador mantem a
    estimativa do LLM nesse caso (graceful degradation).
    """
    try:
        series = await asyncio.to_thread(_fetch_sync, keyword)
    except Exception as e:  # noqa: BLE001 - falha vira None, nunca derruba a pipeline
        log.warning("google_trends.fetch_failed", keyword=keyword, error=str(e))
        return None

    if not series:
        log.warning("google_trends.no_data", keyword=keyword)
        return None

    result = {
        "keyword": keyword,
        "interest_over_time": series,
        "trend_direction": _trend_direction([point["value"] for point in series]),
        "is_mock": False,
    }
    log.info(
        "google_trends.completed",
        keyword=keyword,
        trend_direction=result["trend_direction"],
        points=len(series),
    )
    return result
