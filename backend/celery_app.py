"""Entry point do Celery: app, config e beat schedule.

O beat dispara `scheduled_run` a cada PIPELINE_INTERVAL_SECONDS. A tarefa
so executa de fato a rodada se a pipeline estiver habilitada (start/stop
controlam o flag no Redis).
"""

from celery import Celery
from celery.schedules import crontab

from core.config import settings

celery = Celery(
    "market_intelligence",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["workers.pipeline_worker"],
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
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
