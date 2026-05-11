from celery import Celery
from app.config import get_settings

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
    task_acks_late=True,           # ack after task completes (safer on crashes)
    worker_prefetch_multiplier=1,  # one task at a time per worker
    timezone="UTC",
)
