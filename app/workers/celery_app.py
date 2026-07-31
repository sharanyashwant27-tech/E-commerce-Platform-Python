"""Celery application configuration."""

from celery import Celery

from config.settings import settings

celery_app = Celery(
    "shopsphere",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    # Avoid indefinite hangs when Redis broker is down (common in local/unit tests)
    broker_connection_retry_on_startup=True,
    broker_connection_timeout=2,
    result_backend_transport_options={"socket_timeout": 2, "socket_connect_timeout": 2},
    broker_transport_options={"socket_timeout": 2, "socket_connect_timeout": 2},
)
