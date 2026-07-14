"""Controle de estado da pipeline, compartilhado via Redis.

A API e o worker Celery sao processos diferentes, entao guardamos o
estado (ligado/desligado e ultimo status) no Redis. Tudo degrada
graciosamente: se o Redis estiver fora, retornamos defaults seguros.

Multi-tenancy: cada conta tem suas proprias chaves
(pipeline:{account_id}:enabled/status/running) — ligar/desligar a
pipeline de um cliente nunca afeta os demais.
"""

import json

import redis

from core.config import settings
from core.logging_config import get_logger

log = get_logger("pipeline_control")

# A trava expira sozinha caso uma rodada morra sem liberar (worker reiniciado,
# crash, etc.), evitando que a pipeline trave para sempre.
_RUNNING_LOCK_TTL_SECONDS = 1800


def _client() -> redis.Redis:
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


def _key(account_id: str, suffix: str) -> str:
    return f"pipeline:{account_id}:{suffix}"


def set_enabled(account_id: str, value: bool) -> bool:
    try:
        _client().set(_key(account_id, "enabled"), "1" if value else "0")
        return True
    except Exception as e:  # noqa: BLE001
        log.error("pipeline_control.set_enabled_failed", error=str(e))
        return False


def is_enabled(account_id: str) -> bool:
    try:
        return _client().get(_key(account_id, "enabled")) == "1"
    except Exception as e:  # noqa: BLE001
        log.warning("pipeline_control.is_enabled_failed", error=str(e))
        return False


def enabled_accounts() -> list[str]:
    """Contas com a pipeline continua ligada (para o watchdog do Beat).

    Varre pipeline:*:enabled com SCAN (nao bloqueia o Redis). Se o Redis
    estiver fora, devolve lista vazia — o Beat simplesmente nao dispara nada.
    """
    try:
        client = _client()
        accounts: list[str] = []
        for key in client.scan_iter(match="pipeline:*:enabled", count=100):
            if client.get(key) == "1":
                # pipeline:{account_id}:enabled -> account_id
                accounts.append(key.split(":")[1])
        return accounts
    except Exception as e:  # noqa: BLE001
        log.warning("pipeline_control.enabled_accounts_failed", error=str(e))
        return []


def acquire_run_lock(account_id: str) -> bool:
    """Tenta marcar que uma rodada DESTA conta esta em andamento.

    Retorna True se conseguiu a trava (pode rodar), False se ja ha uma rodada
    em andamento (deve pular). Usada para que o auto-encadeamento e o watchdog
    do Beat nunca rodem duas rodadas ao mesmo tempo. Se o Redis estiver fora,
    degradamos para True (deixa rodar) — o is_enabled ja barra esse caso.
    """
    try:
        # set NX: so grava se a chave ainda nao existe (trava atomica).
        acquired = _client().set(
            _key(account_id, "running"), "1", nx=True, ex=_RUNNING_LOCK_TTL_SECONDS
        )
        return bool(acquired)
    except Exception as e:  # noqa: BLE001
        log.warning("pipeline_control.acquire_run_lock_failed", error=str(e))
        return True


def release_run_lock(account_id: str) -> None:
    """Libera a trava de rodada em andamento da conta."""
    try:
        _client().delete(_key(account_id, "running"))
    except Exception as e:  # noqa: BLE001
        log.warning("pipeline_control.release_run_lock_failed", error=str(e))


def set_status(account_id: str, data: dict) -> None:
    try:
        _client().set(_key(account_id, "status"), json.dumps(data))
    except Exception as e:  # noqa: BLE001
        log.warning("pipeline_control.set_status_failed", error=str(e))


def get_status(account_id: str) -> dict:
    try:
        raw = _client().get(_key(account_id, "status"))
        return json.loads(raw) if raw else {}  # type: ignore[arg-type]
    except Exception as e:  # noqa: BLE001
        log.warning("pipeline_control.get_status_failed", error=str(e))
        return {}


def redis_available() -> bool:
    try:
        return bool(_client().ping())
    except Exception:  # noqa: BLE001
        return False
