"""Controle de estado da pipeline, compartilhado via Redis.

A API e o worker Celery sao processos diferentes, entao guardamos o
estado (ligado/desligado e ultimo status) no Redis. Tudo degrada
graciosamente: se o Redis estiver fora, retornamos defaults seguros.
"""

import json

import redis

from core.config import settings
from core.logging_config import get_logger

log = get_logger("pipeline_control")

_KEY_ENABLED = "pipeline:enabled"
_KEY_STATUS = "pipeline:status"
_KEY_RUNNING = "pipeline:running"

# A trava expira sozinha caso uma rodada morra sem liberar (worker reiniciado,
# crash, etc.), evitando que a pipeline trave para sempre.
_RUNNING_LOCK_TTL_SECONDS = 1800


def _client() -> redis.Redis:
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


def set_enabled(value: bool) -> bool:
    try:
        _client().set(_KEY_ENABLED, "1" if value else "0")
        return True
    except Exception as e:  # noqa: BLE001
        log.error("pipeline_control.set_enabled_failed", error=str(e))
        return False


def is_enabled() -> bool:
    try:
        return _client().get(_KEY_ENABLED) == "1"
    except Exception as e:  # noqa: BLE001
        log.warning("pipeline_control.is_enabled_failed", error=str(e))
        return False


def acquire_run_lock() -> bool:
    """Tenta marcar que uma rodada esta em andamento.

    Retorna True se conseguiu a trava (pode rodar), False se ja ha uma rodada
    em andamento (deve pular). Usada para que o auto-encadeamento e o watchdog
    do Beat nunca rodem duas rodadas ao mesmo tempo. Se o Redis estiver fora,
    degradamos para True (deixa rodar) — o is_enabled ja barra esse caso.
    """
    try:
        # set NX: so grava se a chave ainda nao existe (trava atomica).
        acquired = _client().set(_KEY_RUNNING, "1", nx=True, ex=_RUNNING_LOCK_TTL_SECONDS)
        return bool(acquired)
    except Exception as e:  # noqa: BLE001
        log.warning("pipeline_control.acquire_run_lock_failed", error=str(e))
        return True


def release_run_lock() -> None:
    """Libera a trava de rodada em andamento."""
    try:
        _client().delete(_KEY_RUNNING)
    except Exception as e:  # noqa: BLE001
        log.warning("pipeline_control.release_run_lock_failed", error=str(e))


def set_status(data: dict) -> None:
    try:
        _client().set(_KEY_STATUS, json.dumps(data))
    except Exception as e:  # noqa: BLE001
        log.warning("pipeline_control.set_status_failed", error=str(e))


def get_status() -> dict:
    try:
        raw = _client().get(_KEY_STATUS)
        return json.loads(raw) if raw else {}  # type: ignore[arg-type]
    except Exception as e:  # noqa: BLE001
        log.warning("pipeline_control.get_status_failed", error=str(e))
        return {}


def redis_available() -> bool:
    try:
        return bool(_client().ping())
    except Exception:  # noqa: BLE001
        return False
