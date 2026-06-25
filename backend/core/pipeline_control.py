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


def set_status(data: dict) -> None:
    try:
        _client().set(_KEY_STATUS, json.dumps(data))
    except Exception as e:  # noqa: BLE001
        log.warning("pipeline_control.set_status_failed", error=str(e))


def get_status() -> dict:
    try:
        raw = _client().get(_KEY_STATUS)
        return json.loads(raw) if raw else {}
    except Exception as e:  # noqa: BLE001
        log.warning("pipeline_control.get_status_failed", error=str(e))
        return {}


def redis_available() -> bool:
    try:
        return bool(_client().ping())
    except Exception:  # noqa: BLE001
        return False
