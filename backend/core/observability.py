"""Inicializacao do Sentry (observabilidade).

Degrada graciosamente: sem SENTRY_DSN configurado, e um no-op — nada e
enviado e a aplicacao sobe normalmente. As integracoes FastAPI/Starlette/
Celery do sentry-sdk sao ativadas automaticamente quando os pacotes estao
presentes. Idempotente: pode ser chamada mais de uma vez sem efeito duplo.
"""

import sentry_sdk

from core.config import settings
from core.logging_config import get_logger

log = get_logger("observability")

_initialized = False


def init_sentry() -> bool:
    """Inicializa o Sentry se houver DSN. Retorna True se ativou."""
    global _initialized
    if _initialized:
        return True
    if not settings.sentry_dsn:
        log.info("sentry.disabled")  # sem DSN: no-op, sem erro
        return False
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=False,  # nunca enviar dados pessoais por padrao
    )
    _initialized = True
    log.info("sentry.enabled", environment=settings.environment)
    return True
