"""Optional Celery worker. Off by default. Same Job rows as the thread worker.

Never run the in-process thread worker and a Celery worker against the same
SQLite file at the same time. Prefer Postgres when Celery is enabled.
"""

from __future__ import annotations

import logging

from .modes import WORKER_CELERY

log = logging.getLogger("aigc.studio.jobs.celery")

TASK_EXECUTE = "studio.execute_job"


def _settings():
    from ..config import get_settings

    return get_settings()


def broker_url() -> str:
    url = (_settings().celery_broker_url or "").strip()
    if not url:
        raise RuntimeError(
            "STUDIO_JOB_WORKER=celery requires STUDIO_CELERY_BROKER_URL "
            "(Redis). Celery is opt-in and off by default — the thread worker "
            "is the default."
        )
    return url


def _celery_class():
    try:
        from celery import Celery
    except ImportError as exc:
        raise RuntimeError(
            "Celery extra is not installed. "
            "pip install -e './studio[celery]'. "
            "The default worker remains thread."
        ) from exc
    return Celery


def make_celery():
    Celery = _celery_class()
    application = Celery("aigc_studio", broker=broker_url())
    application.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        task_ignore_result=True,
        timezone="UTC",
        worker_hijack_root_logger=False,
    )
    return application


def _bind_tasks(application):
    @application.task(name=TASK_EXECUTE)
    def execute_job_task(job_id: str) -> str:
        from .runner import execute_job

        log.info("Celery executing job %s (same Job row as the thread worker)", job_id)
        execute_job(None, job_id)
        return job_id

    return execute_job_task


def _try_app():
    try:
        application = make_celery()
        _bind_tasks(application)
        return application
    except Exception as exc:  # noqa: BLE001 — optional extra; CLI may not have Redis
        log.debug("Celery app not constructed: %s", exc)
        return None


app = _try_app()


def send_execute_job(job_id: str) -> None:
    """Push one Job id onto the broker. The worker dequeues the same Job row."""
    settings = _settings()
    mode = (settings.job_worker or "").strip().lower()
    if mode != WORKER_CELERY:
        raise RuntimeError(
            "send_execute_job is only for STUDIO_JOB_WORKER=celery. "
            "Default remains thread."
        )
    url = broker_url()
    database_url = settings.database_url or ""
    if database_url.startswith("sqlite"):
        log.warning(
            "Celery + SQLite is fragile. Do not also run the thread worker "
            "against this database. Prefer the postgres compose profile."
        )
    application = app
    if application is None:
        application = make_celery()
        _bind_tasks(application)
    application.send_task(TASK_EXECUTE, args=[job_id])
    log.info("Queued Celery task %s for job %s via %s", TASK_EXECUTE, job_id, url.split("@")[-1])
