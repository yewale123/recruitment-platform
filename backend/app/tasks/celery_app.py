import logging
from celery import Celery
from app.config import get_settings
from celery.schedules import crontab  # noqa: F401

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

settings = get_settings()

celery_app = Celery(
    "recruitment",
    broker=settings.celery_broker,
    backend=settings.celery_backend,
    include=["app.tasks.scrape_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_expires=86400,          # task results kept for 24 hours
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    timezone="UTC",
    beat_schedule={},
)
