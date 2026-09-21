"""In-process job worker. Celery upgrade: same Job table, swap this loop for a task."""

from __future__ import annotations

import logging
import threading
import time

from ..config import get_settings
from ..database import SessionLocal
from ..models import Job

log = logging.getLogger("aigc.studio.jobs")

_worker: JobWorker | None = None
_lock = threading.Lock()


class JobWorker:
    def __init__(self, *, poll_seconds: float | None = None, force: bool = False):
        self.poll_seconds = poll_seconds
        self.force = force
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def enabled(self) -> bool:
        if self.force:
            return True
        from .modes import WORKER_THREAD, normalize_worker

        return normalize_worker(get_settings().job_worker) == WORKER_THREAD

    def start(self) -> None:
        if not self.enabled:
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="studio-job-worker", daemon=True)
        self._thread.start()
        log.info(
            "Studio job worker started (in-process thread). "
            "Celery is opt-in (STUDIO_JOB_WORKER=celery) and is not running in this process. "
            "Do not also start a Celery worker against the same SQLite file."
        )

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=2)

    def wakeup(self) -> None:
        self._wake.set()

    def _interval(self) -> float:
        if self.poll_seconds is not None:
            return max(0.05, float(self.poll_seconds))
        try:
            return max(0.05, float(get_settings().job_poll_seconds))
        except Exception:
            return 0.25

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                processed = process_one_queued_job()
            except Exception:
                log.exception("Job worker loop failed")
                processed = False
            if processed:
                continue
            self._wake.wait(timeout=self._interval())
            self._wake.clear()

    def run_forever(self) -> None:
        self.force = True
        log.info(
            "Studio job worker polling (standalone thread). "
            "Celery is a separate opt-in process — do not run both against the same SQLite file."
        )
        try:
            self._loop()
        except KeyboardInterrupt:
            self.stop()


def process_one_queued_job() -> bool:
    from .runner import due_comfy_job_id, execute_job, resume_due_comfy_job

    db = SessionLocal()
    try:
        job = (
            db.query(Job)
            .filter(Job.status == "queued")
            .order_by(Job.created_at.asc())
            .first()
        )
        if job:
            job_id = job.id
            kind = "execute"
        else:
            job_id = due_comfy_job_id(db)
            kind = "resume"
    finally:
        db.close()
    if not job_id:
        return False
    if kind == "execute":
        execute_job(None, job_id)
    else:
        resume_due_comfy_job(job_id)
    return True


def get_worker() -> JobWorker | None:
    return _worker


def start_worker() -> JobWorker | None:
    global _worker
    with _lock:
        if _worker is None:
            _worker = JobWorker()
        _worker.start()
        return _worker


def stop_worker() -> None:
    global _worker
    with _lock:
        if _worker is not None:
            _worker.stop()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    from .. import models as _models  # noqa: F401
    from ..database import Base, engine, ensure_schema
    from ..seed import seed_default_org

    Base.metadata.create_all(bind=engine)
    ensure_schema(engine)
    db = SessionLocal()
    try:
        seed_default_org(db)
    finally:
        db.close()
    worker = JobWorker(force=True)
    worker.run_forever()
    # keep import used
    time.sleep(0)
