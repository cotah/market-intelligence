"""Entry point do Celery: app, config e beat schedule.

O beat dispara `scheduled_run` a cada PIPELINE_INTERVAL_SECONDS. A tarefa
so executa de fato a rodada se a pipeline estiver habilitada (start/stop
controlam o flag no Redis).
"""

from celery import Celery
from celery.schedules import crontab
from celery.signals import setup_logging

from core.config import settings
from core.logging_config import configure_logging

celery = Celery(
    "market_intelligence",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["workers.pipeline_worker"],
)


@setup_logging.connect
def _configure_worker_logging(**_kwargs) -> None:
    """Faz o worker e o beat usarem o MESMO structlog da API.

    Sem isto, o Celery configura o logging dele e redireciona o stdout,
    engolindo os logs INFO dos agentes (so passa WARNING+). Resultado: a
    task rodava 'sem logs'. Conectar um receiver a setup_logging tambem
    impede o Celery de sequestrar o logging (worker_hijack_root_logger).
    """
    configure_logging()


celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # Nao deixar o Celery capturar/nivelar o stdout: nossos logs INFO (via
    # structlog -> stdout) precisam sair direto, sem virar WARNING e sumir.
    worker_redirect_stdouts=False,
    beat_schedule={
        # Rodada da pipeline a cada PIPELINE_INTERVAL_SECONDS (so roda se habilitada).
        "pipeline-scheduled-run": {
            "task": "workers.pipeline_worker.scheduled_run",
            "schedule": float(settings.pipeline_interval_seconds),
        },
        # Relatorio diario consolidado, todo dia as 23:00 UTC.
        "daily-report": {
            "task": "workers.pipeline_worker.generate_daily_report_task",
            "schedule": crontab(hour=23, minute=0),
        },
    },
)
